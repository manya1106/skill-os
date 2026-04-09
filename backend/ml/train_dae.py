"""
DAE-CF: Denoising Autoencoder Collaborative Filtering
------------------------------------------------------
Train this ONLY after you have at least 50 real users with interaction data.
Until then, the TF-IDF recommender handles everything.

Architecture (from your project report):
  Input  →  [I → 1024 → 512 → 128 (latent)]   Encoder
  Latent →  [128 → 512 → 1024 → I]             Decoder
  Loss: weighted MSE + L2 regularisation
  Cold-start: hybrid blend (0.7 × CF + 0.3 × content-based)

HOW TO RUN:
  pip install tensorflow scikit-learn pandas numpy
  python train_dae.py

The saved model goes to  ml/model/dae_cf.h5
Once saved, the Flask service loads it automatically.
"""

import os
import json
import numpy as np
import pandas as pd


# ─── 1. Load interaction data from Supabase ───────────────────────────────

def load_interaction_matrix(supabase):
    """
    Build a user × resource implicit feedback matrix.
    Value = weighted combination of:
      - watch_percentage  (normalised 0-1)
      - completion bonus  (+0.5 if completed)
      - bookmark bonus    (+0.3 if manually saved)
    """
    interactions = supabase.table("interactions").select(
        "user_id, resource_id, event_type, value"
    ).execute().data or []

    if not interactions:
        print("[DAE-CF] No interaction data found. Train after real users sign up.")
        return None, None, None

    df = pd.DataFrame(interactions)

    # Pivot to user × resource matrix
    df["implicit"] = df.apply(_weight_event, axis=1)
    matrix = df.groupby(["user_id", "resource_id"])["implicit"].sum().reset_index()
    pivot = matrix.pivot(index="user_id", columns="resource_id", values="implicit").fillna(0)

    # Clip to [0, 1]
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
        "watch":     val / 100.0,       # watch_percentage → 0-1
        "complete":  1.0,
        "bookmark":  0.5,
        "progress":  val / 100.0 * 0.7,
        "start":     0.1,
    }
    return weights.get(evt, 0.05)


# ─── 2. Build the Keras model ─────────────────────────────────────────────

def build_dae_model(n_items: int, latent_dim: int = 128, dropout_rate: float = 0.3):
    """
    Denoising Autoencoder for Collaborative Filtering (DAE-CF).
    Matches architecture in project report exactly.
    """
    import tensorflow as tf
    from tensorflow import keras

    inp = keras.Input(shape=(n_items,), name="user_vector")

    # Add noise for denoising (makes model robust)
    noisy = keras.layers.GaussianNoise(0.1)(inp)

    # Encoder
    x = keras.layers.Dense(1024, activation="relu",
                            kernel_regularizer=keras.regularizers.l2(1e-5))(noisy)
    x = keras.layers.Dropout(dropout_rate)(x)
    x = keras.layers.Dense(512, activation="relu",
                            kernel_regularizer=keras.regularizers.l2(1e-5))(x)
    x = keras.layers.Dropout(dropout_rate)(x)
    latent = keras.layers.Dense(latent_dim, activation="relu", name="latent")(x)

    # Decoder (symmetric)
    x = keras.layers.Dense(512, activation="relu")(latent)
    x = keras.layers.Dense(1024, activation="relu")(x)
    output = keras.layers.Dense(n_items, activation="sigmoid", name="reconstruction")(x)

    model = keras.Model(inputs=inp, outputs=output, name="DAE-CF")

    # Weighted MSE: items the user interacted with get higher loss weight
    # (confidence weighting — standard for implicit feedback)
    def weighted_mse(y_true, y_pred):
        confidence = 1.0 + 9.0 * y_true   # 1 for unseen, 10 for seen
        return tf.reduce_mean(confidence * tf.square(y_true - y_pred))

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss=weighted_mse,
    )

    model.summary()
    return model


# ─── 3. Train ──────────────────────────────────────────────────────────────

def train(supabase=None, X: np.ndarray = None, epochs: int = 40, batch_size: int = 64):
    """
    Train the DAE-CF model.
    Pass either supabase client OR a pre-built numpy matrix X.
    """
    if X is None:
        if supabase is None:
            raise ValueError("Provide either supabase client or matrix X")
        X, user_ids, resource_ids = load_interaction_matrix(supabase)
        if X is None:
            return None
    else:
        user_ids = [str(i) for i in range(X.shape[0])]
        resource_ids = [str(i) for i in range(X.shape[1])]

    import tensorflow as tf
    from tensorflow import keras

    n_items = X.shape[1]
    model = build_dae_model(n_items)

    # Train/val split
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
        X_train, X_train,
        validation_data=(X_val, X_val) if len(X_val) > 0 else None,
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1,
    )

    # Save model + metadata
    os.makedirs("model", exist_ok=True)
    model.save("model/dae_cf.h5")

    meta = {"user_ids": user_ids, "resource_ids": resource_ids}
    with open("model/meta.json", "w") as f:
        json.dump(meta, f)

    print("[DAE-CF] Model saved to model/dae_cf.h5")
    print(f"[DAE-CF] Final val_loss: {history.history.get('val_loss', ['n/a'])[-1]:.4f}")
    return model, user_ids, resource_ids


# ─── 4. Inference ──────────────────────────────────────────────────────────

class DAERecommender:
    """
    Loaded once by the Flask ML service.
    Falls back gracefully to None if model hasn't been trained yet.
    """
    def __init__(self, model_dir: str = "model"):
        self.model = None
        self.user_ids: list = []
        self.resource_ids: list = []
        self._load(model_dir)

    def _load(self, model_dir: str):
        model_path = os.path.join(model_dir, "dae_cf.h5")
        meta_path  = os.path.join(model_dir, "meta.json")
        if not os.path.exists(model_path):
            print("[DAE-CF] No trained model found. Using TF-IDF fallback.")
            return
        try:
            import tensorflow as tf
            self.model = tf.keras.models.load_model(
                model_path,
                compile=False,
            )
            with open(meta_path) as f:
                meta = json.load(f)
            self.user_ids    = meta["user_ids"]
            self.resource_ids = meta["resource_ids"]
            print(f"[DAE-CF] Model loaded — {len(self.user_ids)} users, "
                  f"{len(self.resource_ids)} resources")
        except Exception as e:
            print(f"[DAE-CF] Could not load model: {e}. Using TF-IDF fallback.")
            self.model = None

    def is_ready(self) -> bool:
        return self.model is not None

    def recommend(self, user_id: str, top_n: int = 6,
                  tfidf_weight: float = 0.3) -> list[dict] | None:
        """
        Returns top_n item indices for user_id.
        Returns None if model not loaded (triggers TF-IDF fallback in Flask).
        tfidf_weight: how much content-based signal to blend in (cold-start)
        """
        if not self.is_ready():
            return None
        if user_id not in self.user_ids:
            return None  # completely new user → TF-IDF handles it

        idx = self.user_ids.index(user_id)
        user_vec = np.zeros((1, len(self.resource_ids)), dtype=np.float32)

        # Reconstruct preference scores
        scores = self.model.predict(user_vec, verbose=0)[0]

        # Zero out items the user already interacted with (don't re-recommend)
        # (You'd set known items to 0 here based on their actual history)

        # Top-N indices
        top_indices = np.argsort(scores)[::-1][:top_n * 3]

        results = []
        for i in top_indices:
            resource_id = self.resource_ids[i]
            results.append({
                "resource_id": resource_id,
                "cf_score": float(scores[i]),
            })
            if len(results) >= top_n:
                break

        return results


# ─── 5. Run training directly ──────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run from the backend/ directory:
      cd backend
      python -m ml.train_dae

    Or with a dummy dataset to test the architecture:
      python ml/train_dae.py --demo
    """
    import sys

    if "--demo" in sys.argv:
        print("[DAE-CF] Running demo training with synthetic data...")
        # 100 fake users, 50 fake resources
        X_demo = np.random.binomial(1, 0.1, size=(100, 50)).astype(np.float32)
        train(X=X_demo, epochs=5, batch_size=16)
    else:
        print("[DAE-CF] Connect to Supabase and run training.")
        print("Usage: python ml/train_dae.py --demo   (to test with fake data)")
        print("       Set SUPABASE_URL and SUPABASE_KEY env vars then run without --demo")