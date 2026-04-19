import React, { useState, useEffect } from "react";
import {
  Sparkles, ThumbsDown, ThumbsUp, Plus, Clock, Zap,
  AlertTriangle, ChevronDown, ChevronUp, Check,
} from "lucide-react";
import { PlatformBadge } from "./ui";
import { api } from "../api";

export default function Recommendations() {
  const [recs, setRecs]           = useState([]);
  const [struggles, setStruggles] = useState([]);
  const [model, setModel]         = useState("");
  const [loading, setLoading]     = useState(true);
  const [dismissed, setDismissed] = useState(new Set());
  const [saved, setSaved]         = useState(new Set());
  const [liked, setLiked]         = useState(new Set());
  const [showStruggles, setShowStruggles] = useState(true);
  const [feedback, setFeedback]   = useState({});  // { id: "like"|"dislike"|"save" }

  useEffect(() => {
    async function load() {
      try {
        const [recData, struggleData] = await Promise.all([
          api.recommendations(),
          api.struggles(),
        ]);
        setRecs(recData.recommendations ?? []);
        setModel(recData.model ?? "");
        setStruggles(struggleData.resources ?? []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const visible = recs.filter(r => !dismissed.has(r.id));

  async function sendFeedback(rec, action) {
    // Optimistic UI update
    if (action === "save") {
      setSaved(prev => { const n = new Set(prev); n.has(rec.id) ? n.delete(rec.id) : n.add(rec.id); return n; });
    } else if (action === "like") {
      setLiked(prev => { const n = new Set(prev); n.has(rec.id) ? n.delete(rec.id) : n.add(rec.id); return n; });
    } else if (action === "dislike") {
      setDismissed(prev => new Set([...prev, rec.id]));
    }

    setFeedback(prev => ({ ...prev, [rec.id]: action }));

    // Send to backend — this feeds the DAE-CF retraining pipeline
    try {
      await api.recommendationFeedback({
        resource_id: rec.id,
        action,
        platform: rec.platform,
        tags: rec.tags ?? [],
      });
    } catch (err) {
      console.error("Feedback error:", err);
    }
  }

  const scoreColor = s =>
    s >= 90 ? "text-green-600 bg-green-50" :
    s >= 80 ? "text-indigo-600 bg-indigo-50" :
              "text-amber-600 bg-amber-50";

  return (
    <div style={{ padding: "2rem", maxWidth: 960, margin: "0 auto" }}>
      {/* Header banner */}
      <div style={{
        background: "linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%)",
        border: "0.5px solid #DDD6FE",
        borderRadius: "var(--border-radius-lg)",
        padding: "20px 24px", marginBottom: 24,
        display: "flex", alignItems: "flex-start", gap: 16,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          background: "#4F46E5",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Sparkles style={{ width: 20, height: 20, color: "white" }} />
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ margin: "0 0 3px", fontSize: 14, fontWeight: 500,
            color: "var(--color-text-primary)" }}>
            Personalised for you
          </p>
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-secondary)" }}>
            Like or save recommendations to improve future suggestions.
            Your feedback trains the recommendation model directly.
          </p>
        </div>
        {model && (
          <span style={{
            fontSize: 10, fontWeight: 500, padding: "3px 10px", borderRadius: 20, flexShrink: 0,
            background: model === "dae_cf" ? "#EAF3DE" : "#EEF2FF",
            color: model === "dae_cf" ? "#3B6D11" : "#4338CA",
          }}>
            {model === "dae_cf" ? "DAE-CF model ✓" : model === "tfidf" ? "TF-IDF model" : "curated"}
          </span>
        )}
      </div>

      {/* Struggle panel */}
      {struggles.length > 0 && (
        <div style={{
          background: "#FFFBEB",
          border: "0.5px solid #FDE68A",
          borderRadius: "var(--border-radius-lg)",
          padding: "16px 20px", marginBottom: 24,
        }}>
          <button
            onClick={() => setShowStruggles(s => !s)}
            style={{
              width: "100%", display: "flex", alignItems: "center",
              justifyContent: "space-between", background: "none",
              border: "none", cursor: "pointer", padding: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <AlertTriangle style={{ width: 18, height: 18, color: "#D97706", flexShrink: 0 }} />
              <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#92400E" }}>
                Struggling with {struggles.length} resource{struggles.length > 1 ? "s" : ""}
              </p>
            </div>
            {showStruggles
              ? <ChevronUp style={{ width: 16, height: 16, color: "#D97706" }} />
              : <ChevronDown style={{ width: 16, height: 16, color: "#D97706" }} />
            }
          </button>
          {showStruggles && (
            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
              {struggles.map(s => (
                <div key={s.resource_id} style={{
                  background: "white", borderRadius: "var(--border-radius-md)",
                  padding: "12px 14px", border: "0.5px solid #FDE68A",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <p style={{ margin: 0, fontSize: 13, fontWeight: 500,
                      color: "var(--color-text-primary)" }}>{s.title}</p>
                    <span style={{
                      fontSize: 10, fontWeight: 500, color: "#B45309",
                      marginLeft: 8, flexShrink: 0,
                    }}>
                      Score: {Math.round(s.struggle_score * 100)}%
                    </span>
                  </div>
                  {(s.interventions ?? []).map((tip, i) => (
                    <p key={i} style={{
                      margin: "3px 0 0", fontSize: 12,
                      color: "var(--color-text-secondary)",
                      display: "flex", gap: 6,
                    }}>
                      <span style={{ color: "#D97706", flexShrink: 0 }}>→</span>{tip}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          {[1,2,3,4,5,6].map(i => (
            <div key={i} style={{
              background: "var(--color-background-primary)",
              border: "0.5px solid var(--color-border-tertiary)",
              borderRadius: "var(--border-radius-lg)",
              padding: 20, animation: "pulse 1.5s ease-in-out infinite",
            }}>
              <div style={{ height: 12, background: "var(--color-background-secondary)", borderRadius: 4, width: "33%", marginBottom: 10 }} />
              <div style={{ height: 16, background: "var(--color-background-secondary)", borderRadius: 4, width: "100%", marginBottom: 6 }} />
              <div style={{ height: 12, background: "var(--color-background-secondary)", borderRadius: 4, width: "66%" }} />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && visible.length === 0 && (
        <div style={{
          textAlign: "center", padding: "5rem 0",
          color: "var(--color-text-tertiary)",
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✨</div>
          <p style={{ margin: "0 0 4px", fontWeight: 500, color: "var(--color-text-secondary)" }}>
            All caught up!
          </p>
          <p style={{ margin: 0, fontSize: 13 }}>
            Check back later for fresh recommendations.
          </p>
        </div>
      )}

      {/* Recommendation cards */}
      {!loading && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 14,
        }}>
          {visible.map(rec => (
            <RecCard key={rec.id} rec={rec}
              isSaved={saved.has(rec.id)}
              isLiked={liked.has(rec.id)}
              onSave={() => sendFeedback(rec, "save")}
              onLike={() => sendFeedback(rec, "like")}
              onDislike={() => sendFeedback(rec, "dislike")}
            />
          ))}
        </div>
      )}

      {/* Feedback note */}
      {!loading && recs.length > 0 && (
        <p style={{
          fontSize: 11, color: "var(--color-text-tertiary)",
          textAlign: "center", marginTop: 20,
        }}>
          👍 Like or 💾 Save to train the model · 👎 Dislike to remove and flag
        </p>
      )}
    </div>
  );
}

function RecCard({ rec, isSaved, isLiked, onSave, onLike, onDislike }) {
  const score = rec.match_score ?? 0;
  const scoreStyle = {
    fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 20,
    background: score >= 90 ? "#EAF3DE" : score >= 80 ? "#EEF2FF" : "#FAEEDA",
    color:      score >= 90 ? "#3B6D11" : score >= 80 ? "#4338CA" : "#854F0A",
  };

  return (
    <div style={{
      background: "var(--color-background-primary)",
      border: "0.5px solid var(--color-border-tertiary)",
      borderRadius: "var(--border-radius-lg)",
      padding: 18,
      display: "flex", flexDirection: "column", gap: 10,
      transition: "box-shadow 0.2s",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <PlatformBadge platform={rec.platform} />
        <span style={scoreStyle}>{score}%</span>
      </div>

      <p style={{
        margin: 0, fontSize: 13, fontWeight: 500,
        color: "var(--color-text-primary)", lineHeight: 1.4,
      }}>
        {rec.title}
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
        {rec.duration && (
          <span style={{
            display: "flex", alignItems: "center", gap: 3,
            fontSize: 11, color: "var(--color-text-secondary)",
          }}>
            <Clock style={{ width: 12, height: 12 }} /> {rec.duration}
          </span>
        )}
        {(rec.tags ?? []).slice(0, 3).map(t => (
          <span key={t} style={{
            fontSize: 10, padding: "1px 7px", borderRadius: 20,
            background: "var(--color-background-secondary)",
            color: "var(--color-text-secondary)",
          }}>
            {t}
          </span>
        ))}
      </div>

      {rec.reason && (
        <p style={{
          margin: 0, fontSize: 11, color: "#4F46E5",
          display: "flex", alignItems: "center", gap: 4,
        }}>
          <Zap style={{ width: 11, height: 11 }} /> {rec.reason}
        </p>
      )}

      {/* Actions */}
      <div style={{
        display: "flex", gap: 6, marginTop: "auto",
        paddingTop: 10, borderTop: "0.5px solid var(--color-border-tertiary)",
      }}>
        {/* Like */}
        <button onClick={onLike} style={{
          flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
          padding: "6px 0", borderRadius: "var(--border-radius-md)",
          border: `0.5px solid ${isLiked ? "#A5B4FC" : "var(--color-border-tertiary)"}`,
          background: isLiked ? "#EEF2FF" : "transparent",
          color: isLiked ? "#4338CA" : "var(--color-text-secondary)",
          fontSize: 12, cursor: "pointer", transition: "all 0.15s",
        }}>
          <ThumbsUp style={{ width: 13, height: 13 }} />
          {isLiked ? "Liked" : "Like"}
        </button>

        {/* Save */}
        <button onClick={onSave} style={{
          flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
          padding: "6px 0", borderRadius: "var(--border-radius-md)",
          border: `0.5px solid ${isSaved ? "#4F46E5" : "var(--color-border-tertiary)"}`,
          background: isSaved ? "#4F46E5" : "transparent",
          color: isSaved ? "white" : "var(--color-text-secondary)",
          fontSize: 12, cursor: "pointer", transition: "all 0.15s", fontWeight: isSaved ? 500 : 400,
        }}>
          {isSaved ? <Check style={{ width: 13, height: 13 }} /> : <Plus style={{ width: 13, height: 13 }} />}
          {isSaved ? "Saved" : "Save"}
        </button>

        {/* Dislike */}
        <button onClick={onDislike} style={{
          padding: "6px 8px", borderRadius: "var(--border-radius-md)",
          border: "0.5px solid var(--color-border-tertiary)",
          background: "transparent",
          color: "var(--color-text-tertiary)",
          cursor: "pointer", transition: "all 0.15s",
          display: "flex", alignItems: "center",
        }}
          title="Not interested"
        >
          <ThumbsDown style={{ width: 13, height: 13 }} />
        </button>
      </div>
    </div>
  );
}
