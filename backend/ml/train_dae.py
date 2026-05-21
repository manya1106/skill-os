"""
DAE-CF: Denoising Autoencoder Collaborative Filtering
------------------------------------------------------

Architecture:
  Input  →  [I → 1024 → 512 → 128 (latent)]   Encoder
  Latent →  [128 → 512 → 1024 → I]             Decoder

Inference uses each user's actual interaction vector (not zeros).
Hybrid blend: 0.7 × CF + 0.3 × TF-IDF (configurable in app.py).

Run from backend/:
  python -m ml.train_dae --demo
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Optional, List, Dict

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")


# ─── 1. Load interaction data ────────────────────────────────────────────────

def load_interaction_matrix(supabase):
    """Build user × resource implicit feedback matrix from Supabase."""
    interactions = supabase.table("interactions").select(
        "user_id, resource_id, event_type, value"
    ).execute().data or []

    if not interactions:
        print("[DAE-CF] No interaction data found. Train after real users sign up.")
        return None, None, None

    df = pd.DataFrame(interactions)
    df["implicit"] = df.apply(_weight_event, axis=1)
    matrix = df.groupby(["user_id", "resource_id"])["implicit"].sum().reset_index()
    pivot = matrix.pivot(
        index="user_id", columns="resource_id", values="implicit"
    ).fillna(0)
    pivot = pivot.clip(0, 1)

    user_ids = list(pivot.index)
    resource_ids = list(pivot.columns)
    X = pivot.values.astype(np.float32)

    print(f"[DAE-CF] Matrix: {X.shape[0]} users × {X.shape[1]} resources")
    return X, user_ids, resource_ids


def _weight_event(row) -> float:
    evt = row.get("event_type", "")
    val = float(row.get("value") or 0)
    weights = {
        "watch": val / 100.0,
        "complete": 1.0,
        "bookmark": 0.5,
        "progress": val / 100.0 * 0.7,
        "start": 0.1,
    }
    return weights.get(evt, 0.05)


# ─── 2. Model architecture ───────────────────────────────────────────────────

def build_dae_model(n_items: int, latent_dim: int = 128, dropout_rate: float = 0.3):
    """Encoder 1024 → 512 → 128, decoder mirrored."""
    import tensorflow as tf
    from tensorflow import keras

    inp = keras.Input(shape=(n_items,), name="user_vector")
    noisy = keras.layers.GaussianNoise(0.1)(inp)

    x = keras.layers.Dense(
        1024, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-5)
    )(noisy)
    x = keras.layers.Dropout(dropout_rate)(x)
    x = keras.layers.Dense(
        512, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-5)
    )(x)
    x = keras.layers.Dropout(dropout_rate)(x)
    latent = keras.layers.Dense(latent_dim, activation="relu", name="latent")(x)

    x = keras.layers.Dense(512, activation="relu")(latent)
    x = keras.layers.Dense(1024, activation="relu")(x)
    output = keras.layers.Dense(n_items, activation="sigmoid", name="reconstruction")(x)

    model = keras.Model(inputs=inp, outputs=output, name="DAE-CF")

    def weighted_mse(y_true, y_pred):
        confidence = 1.0 + 9.0 * y_true
        return tf.reduce_mean(confidence * tf.square(y_true - y_pred))

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss=weighted_mse,
    )
    model.summary()
    return model


# ─── 3. Training ───────────────────────────────────────────────────────────────

def train(
    supabase=None,
    X: np.ndarray = None,
    epochs: int = 40,
    batch_size: int = 64,
    model_dir: str = None,
):
    """Train DAE-CF and save to model_dir (default: ml/model/)."""
    model_dir = model_dir or DEFAULT_MODEL_DIR
    os.makedirs(model_dir, exist_ok=True)

    if X is None:
        if supabase is None:
            raise ValueError("Provide either supabase client or matrix X")
        X, user_ids, resource_ids = load_interaction_matrix(supabase)
        if X is None:
            return None
    else:
        user_ids = [str(i) for i in range(X.shape[0])]
        resource_ids = [str(i) for i in range(X.shape[1])]

    from tensorflow import keras

    n_items = X.shape[1]
    model = build_dae_model(n_items)

    split = max(1, int(len(X) * 0.9))
    X_train, X_val = X[:split], X[split:]

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5
        ),
    ]

    history = model.fit(
        X_train,
        X_train,
        validation_data=(X_val, X_val) if len(X_val) > 0 else None,
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1,
    )

    model_path = os.path.join(model_dir, "dae_cf.h5")
    meta_path = os.path.join(model_dir, "meta.json")
    model.save(model_path)

    meta = {"user_ids": user_ids, "resource_ids": resource_ids}
    with open(meta_path, "w") as f:
        json.dump(meta, f)

    print(f"[DAE-CF] Model saved to {model_path}")
    val_loss = history.history.get("val_loss", ["n/a"])[-1]
    print(f"[DAE-CF] Final val_loss: {val_loss:.4f}" if isinstance(val_loss, float) else f"[DAE-CF] Final val_loss: {val_loss}")
    return model, user_ids, resource_ids


# ─── 4. Inference ──────────────────────────────────────────────────────────────

class DAERecommender:
    """
    DAE-CF inference with real user interaction vectors (not zeros).
    Supports optional TF-IDF hybrid blending at inference time.
    """

    def __init__(self, model_dir: str = None, supabase=None):
        self.model = None
        self.user_ids: list = []
        self.resource_ids: list = []
        self.supabase = supabase
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        self._load(self.model_dir)

    def _load(self, model_dir: str):
        model_path = os.path.join(model_dir, "dae_cf.h5")
        meta_path = os.path.join(model_dir, "meta.json")

        if not os.path.exists(model_path):
            print("[DAE-CF] No trained model found. Using TF-IDF fallback.")
            return

        try:
            import tensorflow as tf

            self.model = tf.keras.models.load_model(model_path, compile=False)
            with open(meta_path) as f:
                meta = json.load(f)
            self.user_ids = meta["user_ids"]
            self.resource_ids = meta["resource_ids"]
            print(
                f"[DAE-CF] Model loaded — {len(self.user_ids)} users, "
                f"{len(self.resource_ids)} resources"
            )
        except Exception as e:
            print(f"[DAE-CF] Could not load model: {e}. Using TF-IDF fallback.")
            self.model = None

    def is_ready(self) -> bool:
        return self.model is not None

    def _build_user_interaction_vector(self, user_id: str) -> np.ndarray:
        """Embed user interaction history as a sparse resource vector."""
        if not self.supabase:
            return np.ones(len(self.resource_ids), dtype=np.float32) * 0.1

        try:
            interactions = (
                self.supabase.table("interactions")
                .select("resource_id, event_type, value")
                .eq("user_id", user_id)
                .execute()
            )

            user_vec = np.zeros(len(self.resource_ids), dtype=np.float32)
            if not interactions.data:
                return user_vec + 0.1

            resource_id_to_idx = {
                rid: i for i, rid in enumerate(self.resource_ids)
            }
            resource_scores: Dict[str, float] = {}

            for evt in interactions.data:
                rid = evt["resource_id"]
                if rid not in resource_id_to_idx:
                    continue

                evt_type = evt.get("event_type", "")
                value = float(evt.get("value") or 0)

                if evt_type == "watch":
                    strength = value / 100.0
                elif evt_type == "complete":
                    strength = 1.0
                elif evt_type == "bookmark":
                    strength = 0.5
                elif evt_type == "progress":
                    strength = (value / 100.0) * 0.7
                elif evt_type == "start":
                    strength = 0.1
                else:
                    strength = 0.05

                current = resource_scores.get(rid, 0)
                resource_scores[rid] = min(1.0, current + strength)

            for rid, score in resource_scores.items():
                user_vec[resource_id_to_idx[rid]] = score

            return user_vec

        except Exception as e:
            print(f"[DAE-CF] Failed to build interaction vector for {user_id}: {e}")
            return np.ones(len(self.resource_ids), dtype=np.float32) * 0.1

    def _seen_resources(self, user_id: str) -> set:
        if not self.supabase:
            return set()
        try:
            resp = (
                self.supabase.table("interactions")
                .select("resource_id")
                .eq("user_id", user_id)
                .execute()
            )
            return {i["resource_id"] for i in (resp.data or [])}
        except Exception:
            return set()

    def recommend(
        self,
        user_id: str,
        top_n: int = 6,
        tfidf_weight: float = 0.3,
        tfidf_scores: Optional[Dict[str, float]] = None,
    ) -> Optional[List[dict]]:
        """
        Personalized recommendations using actual user history at inference.

        Returns list of {resource_id, cf_score, tfidf_score, final_score} or None.
        """
        if not self.is_ready():
            return None

        if user_id not in self.user_ids:
            seen = self._seen_resources(user_id)
            known = [r for r in seen if r in self.resource_ids]
            if not known:
                return None

        try:
            user_vec = self._build_user_interaction_vector(user_id)
            user_vec = np.expand_dims(user_vec, axis=0).astype(np.float32)

            cf_scores = self.model.predict(user_vec, verbose=0)[0]
            seen_resources = self._seen_resources(user_id)

            results = []
            for i, rid in enumerate(self.resource_ids):
                if rid in seen_resources:
                    continue

                cf_score = float(cf_scores[i])

                if tfidf_scores and tfidf_weight > 0:
                    tfidf_score = float(tfidf_scores.get(rid, 0.0))
                    final_score = (1 - tfidf_weight) * cf_score + tfidf_weight * tfidf_score
                else:
                    tfidf_score = None
                    final_score = cf_score

                results.append({
                    "resource_id": rid,
                    "cf_score": cf_score,
                    "tfidf_score": tfidf_score,
                    "final_score": final_score,
                })

            results.sort(key=lambda x: x["final_score"], reverse=True)
            return results[:top_n]

        except Exception as e:
            print(f"[DAE-CF] Inference failed for {user_id}: {e}")
            return None


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        print("[DAE-CF] Demo training with synthetic data...")
        X_demo = np.random.binomial(1, 0.1, size=(100, 50)).astype(np.float32)
        train(X=X_demo, epochs=5, batch_size=16)
    else:
        from dotenv import load_dotenv
        from supabase import create_client

        load_dotenv()
        sb = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_KEY", ""),
        )
        train(supabase=sb)
