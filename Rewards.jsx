import React, { useState, useEffect } from "react";
import { Trophy, Star, Flame, Zap, Lock } from "lucide-react";
import { api } from "../api";

function XPBar({ xp, xpToNext, level }) {
  const total = xp + xpToNext;
  const pct = Math.round((xp / total) * 100);

  return (
    <div style={{
      background: "linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4c1d95 100%)",
      borderRadius: "var(--border-radius-lg)", padding: "28px 32px",
      color: "white", marginBottom: 24, position: "relative", overflow: "hidden",
    }}>
      {/* Background decoration */}
      <div style={{
        position: "absolute", top: -40, right: -40,
        width: 160, height: 160, borderRadius: "50%",
        background: "rgba(255,255,255,0.04)",
      }} />
      <div style={{
        position: "absolute", top: 20, right: 20,
        width: 80, height: 80, borderRadius: "50%",
        background: "rgba(255,255,255,0.04)",
      }} />

      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 20 }}>
        <div style={{
          width: 48, height: 48, borderRadius: 12,
          background: "rgba(255,255,255,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22, flexShrink: 0,
        }}>
          <Trophy style={{ width: 24, height: 24 }} />
        </div>
        <div>
          <p style={{ margin: "0 0 2px", fontSize: 13, opacity: 0.7 }}>Current level</p>
          <p style={{ margin: 0, fontSize: 28, fontWeight: 500, lineHeight: 1 }}>
            Level {level}
          </p>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <p style={{ margin: "0 0 2px", fontSize: 13, opacity: 0.7 }}>Total XP</p>
          <p style={{ margin: 0, fontSize: 22, fontWeight: 500 }}>
            {xp.toLocaleString()}
          </p>
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, opacity: 0.7, marginBottom: 6 }}>
          <span>Level {level}</span>
          <span>{xpToNext.toLocaleString()} XP to level {level + 1}</span>
        </div>
        <div style={{ background: "rgba(255,255,255,0.2)", borderRadius: 8, height: 10, overflow: "hidden" }}>
          <div style={{
            width: `${pct}%`, height: "100%",
            background: "linear-gradient(90deg, #a5b4fc, #ffffff)",
            borderRadius: 8, transition: "width 0.6s ease",
          }} />
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, fontSize: 13, opacity: 0.75 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <Star style={{ width: 14, height: 14 }} fill="currentColor" />
          {xp.toLocaleString()} XP earned
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <Zap style={{ width: 14, height: 14 }} fill="currentColor" />
          {pct}% to next level
        </span>
      </div>
    </div>
  );
}

function AchievementCard({ ach }) {
  return (
    <div style={{
      background: ach.unlocked
        ? "var(--color-background-primary)"
        : "var(--color-background-secondary)",
      border: ach.unlocked
        ? "0.5px solid var(--color-border-secondary)"
        : "0.5px solid var(--color-border-tertiary)",
      borderRadius: "var(--border-radius-lg)",
      padding: "16px",
      opacity: ach.unlocked ? 1 : 0.55,
      transition: "all 0.2s",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Unlocked glow accent */}
      {ach.unlocked && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 2,
          background: "linear-gradient(90deg, #818CF8, #A78BFA)",
          borderRadius: "12px 12px 0 0",
        }} />
      )}

      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          background: ach.unlocked
            ? "linear-gradient(135deg, #EEF2FF, #DDD6FE)"
            : "var(--color-background-secondary)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22,
          border: ach.unlocked ? "0.5px solid #C7D2FE" : "0.5px solid var(--color-border-tertiary)",
        }}>
          {ach.unlocked ? ach.icon : <Lock style={{ width: 16, height: 16, opacity: 0.4 }} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
            <p style={{
              margin: 0, fontSize: 13, fontWeight: 500,
              color: ach.unlocked ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>
              {ach.title}
            </p>
            {ach.xp > 0 && (
              <span style={{
                fontSize: 10, fontWeight: 500, padding: "1px 6px",
                borderRadius: 20, flexShrink: 0, marginLeft: 6,
                background: ach.unlocked ? "#EEF2FF" : "var(--color-background-secondary)",
                color: ach.unlocked ? "#4F46E5" : "var(--color-text-tertiary)",
              }}>
                +{ach.xp} XP
              </span>
            )}
          </div>
          <p style={{
            margin: 0, fontSize: 12,
            color: "var(--color-text-tertiary)",
            lineHeight: 1.4,
          }}>
            {ach.desc}
          </p>
          {ach.unlocked && ach.unlocked_at && (
            <p style={{
              margin: "6px 0 0", fontSize: 10,
              color: "var(--color-text-tertiary)",
            }}>
              Unlocked {new Date(ach.unlocked_at).toLocaleDateString("en-IN", {
                day: "numeric", month: "short", year: "numeric",
              })}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Rewards({ user }) {
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading]           = useState(true);

  useEffect(() => {
    api.achievements()
      .then(setAchievements)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const unlocked = achievements.filter(a => a.unlocked);
  const locked   = achievements.filter(a => !a.unlocked);

  const xp       = user?.xp       ?? 0;
  const xpToNext = user?.xp_to_next ?? 968;
  const level    = user?.level    ?? 1;
  const streak   = user?.streak   ?? 0;

  // XP earning guide — what earns what
  const XP_GUIDE = [
    { action: "Daily login",              xp: 15 },
    { action: "Add a resource",           xp: 10 },
    { action: "Start a resource",         xp:  5 },
    { action: "Complete a resource",      xp: 50 },
    { action: "Flashcard review (Good)",  xp:  5 },
    { action: "Flashcard review (Easy)",  xp:  8 },
    { action: "7-day streak",             xp: 100 },
    { action: "30-day streak",            xp: 500 },
  ];

  return (
    <div style={{ padding: "2rem", maxWidth: 820, margin: "0 auto" }}>

      {/* XP / Level banner */}
      <XPBar xp={xp} xpToNext={xpToNext} level={level} />

      {/* Streak callout */}
      {streak > 0 && (
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          background: "#FFF7ED",
          border: "0.5px solid #FDE68A",
          borderRadius: "var(--border-radius-md)",
          padding: "12px 16px", marginBottom: 24,
        }}>
          <Flame style={{ width: 20, height: 20, color: "#F59E0B", flexShrink: 0 }} />
          <div>
            <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#92400E" }}>
              {streak}-day streak!
            </p>
            <p style={{ margin: 0, fontSize: 12, color: "#B45309" }}>
              {streak >= 7
                ? "Week warrior — keep it going!"
                : `${7 - streak} more days for the 7-day streak bonus (+100 XP)`}
            </p>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 24, alignItems: "start" }}>

        {/* Achievements */}
        <div>
          {/* Unlocked */}
          {unlocked.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <p style={{
                fontSize: 12, fontWeight: 500, textTransform: "uppercase",
                letterSpacing: "0.06em", color: "var(--color-text-tertiary)",
                margin: "0 0 12px",
              }}>
                Unlocked ({unlocked.length})
              </p>
              <div style={{ display: "grid", gap: 10 }}>
                {unlocked.map(a => <AchievementCard key={a.id} ach={a} />)}
              </div>
            </div>
          )}

          {/* Locked */}
          {locked.length > 0 && (
            <div>
              <p style={{
                fontSize: 12, fontWeight: 500, textTransform: "uppercase",
                letterSpacing: "0.06em", color: "var(--color-text-tertiary)",
                margin: "0 0 12px",
              }}>
                Locked ({locked.length})
              </p>
              <div style={{ display: "grid", gap: 10 }}>
                {locked.map(a => <AchievementCard key={a.id} ach={a} />)}
              </div>
            </div>
          )}

          {loading && (
            <p style={{ fontSize: 13, color: "var(--color-text-tertiary)" }}>Loading…</p>
          )}
        </div>

        {/* XP guide sidebar */}
        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "16px 18px",
          position: "sticky", top: 24,
        }}>
          <p style={{ fontSize: 13, fontWeight: 500, margin: "0 0 14px",
            color: "var(--color-text-primary)" }}>
            How to earn XP
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {XP_GUIDE.map(item => (
              <div key={item.action} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
                  {item.action}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 500, padding: "1px 7px", borderRadius: 20,
                  background: "#EEF2FF", color: "#4338CA",
                }}>
                  +{item.xp}
                </span>
              </div>
            ))}
          </div>
          <div style={{
            marginTop: 16, padding: "10px 12px",
            background: "var(--color-background-secondary)",
            borderRadius: "var(--border-radius-md)",
            fontSize: 11, color: "var(--color-text-tertiary)", lineHeight: 1.5,
          }}>
            XP is awarded automatically when you perform actions in SkillOS. 
            Levels follow a quadratic curve — each level requires more effort than the last.
          </div>
        </div>
      </div>
    </div>
  );
}
