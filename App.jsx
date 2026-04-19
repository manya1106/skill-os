// App.jsx — key changes from previous version:
// 1. Analytics page added to nav (replaces old static rewards page logic)
// 2. Rewards now gets real achievements from DB
// 3. XP/streak updated on every login via backend
// 4. _xp field from resource mutations reflected in user state

import React, { useState, useEffect, useCallback } from "react";
import {
  Mail, Lock, Eye, EyeOff, ArrowRight, Zap,
  Bell, LayoutDashboard, BookOpen, Trophy, LogOut,
  Star, Flame, Sparkles, Layers, Users, User, BarChart2,
} from "lucide-react";

import { api } from "./api";
import MyLearning      from "./components/MyLearning";
import Recommendations from "./components/Recommendations";
import Flashcards      from "./components/Flashcards";
import StudyBuddies    from "./components/StudyBuddies";
import Analytics       from "./components/Analytics";
import Rewards         from "./components/Rewards";

const NAV = [
  { id: "dashboard",       label: "Dashboard",     Icon: LayoutDashboard },
  { id: "my-learning",     label: "My learning",   Icon: BookOpen        },
  { id: "recommendations", label: "Recommended",   Icon: Sparkles        },
  { id: "flashcards",      label: "Flashcards",    Icon: Layers          },
  { id: "buddies",         label: "Study buddies", Icon: Users           },
  { id: "analytics",       label: "Analytics",     Icon: BarChart2       },
  { id: "rewards",         label: "Rewards",       Icon: Trophy          },
];

// ── XP toast notification ─────────────────────────────────────────────────────
function XPToast({ xp, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2200);
    return () => clearTimeout(t);
  }, []);
  return (
    <div style={{
      position: "fixed", bottom: 24, right: 24, zIndex: 9999,
      background: "#312E81", color: "white",
      padding: "10px 18px", borderRadius: 12,
      fontSize: 13, fontWeight: 500,
      display: "flex", alignItems: "center", gap: 8,
      animation: "slideUp 0.3s ease",
      boxShadow: "0 4px 24px rgba(0,0,0,0.18)",
    }}>
      <Star style={{ width: 14, height: 14, fill: "#FCD34D", stroke: "none" }} />
      +{xp} XP earned!
    </div>
  );
}

// ── Shell ──────────────────────────────────────────────────────────────────────
function Shell({ page, setPage, onLogout, user, toast, children }) {
  const initials = user?.name
    ? user.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()
    : "??";

  return (
    <div style={{ display: "flex", height: "100vh", width: "100%", overflow: "hidden" }}>
      <style>{`
        @keyframes slideUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:none; } }
        * { box-sizing: border-box; }
        body { margin: 0; font-family: var(--font-sans); background: var(--color-background-tertiary); color: var(--color-text-primary); }
        ::-webkit-scrollbar { width: 5px; } ::-webkit-scrollbar-thumb { background: var(--color-border-secondary); border-radius: 4px; }
      `}</style>

      {/* Sidebar */}
      <aside style={{
        width: 224, background: "var(--color-background-primary)",
        borderRight: "0.5px solid var(--color-border-tertiary)",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div>
          {/* Logo */}
          <div style={{
            height: 56, display: "flex", alignItems: "center", padding: "0 20px",
            borderBottom: "0.5px solid var(--color-border-tertiary)",
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: "linear-gradient(135deg, #4F46E5, #7C3AED)",
              display: "flex", alignItems: "center", justifyContent: "center", marginRight: 8,
            }}>
              <Zap style={{ width: 14, height: 14, color: "white" }} fill="white" />
            </div>
            <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.3px" }}>
              Skill<span style={{ color: "#4F46E5" }}>OS</span>
            </span>
          </div>

          {/* Nav */}
          <nav style={{ padding: "10px 8px" }}>
            {NAV.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setPage(id)} style={{
                width: "100%", display: "flex", alignItems: "center", gap: 10,
                padding: "8px 12px", borderRadius: 10, marginBottom: 1,
                fontSize: 13, fontWeight: page === id ? 500 : 400,
                background: page === id ? "var(--color-background-info)" : "transparent",
                color: page === id ? "var(--color-text-info)" : "var(--color-text-secondary)",
                border: "none", cursor: "pointer", transition: "all 0.15s",
                textAlign: "left",
              }}>
                <Icon style={{ width: 15, height: 15, flexShrink: 0 }} />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* User footer */}
        <div style={{ padding: "12px 8px", borderTop: "0.5px solid var(--color-border-tertiary)" }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "8px 10px", borderRadius: 10,
            background: "var(--color-background-secondary)", marginBottom: 6,
          }}>
            <div style={{
              width: 34, height: 34, borderRadius: "50%",
              background: "var(--color-background-info)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700, color: "var(--color-text-info)", flexShrink: 0,
            }}>
              {initials}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user?.name ?? "—"}
              </p>
              <p style={{ margin: 0, fontSize: 11, color: "var(--color-text-tertiary)" }}>
                Lv {user?.level ?? 1} · {user?.streak ?? 0}d 🔥
              </p>
            </div>
          </div>
          <button onClick={onLogout} style={{
            width: "100%", display: "flex", alignItems: "center", gap: 8,
            padding: "7px 10px", borderRadius: 10, fontSize: 12,
            color: "var(--color-text-tertiary)", background: "none",
            border: "none", cursor: "pointer",
            transition: "all 0.15s",
          }}>
            <LogOut style={{ width: 13, height: 13 }} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <header style={{
          height: 56, background: "var(--color-background-primary)",
          borderBottom: "0.5px solid var(--color-border-tertiary)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 24px", flexShrink: 0,
        }}>
          <h1 style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>
            {NAV.find(n => n.id === page)?.label ?? "Dashboard"}
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              background: "var(--color-background-secondary)",
              padding: "5px 12px", borderRadius: 20, fontSize: 12,
            }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#F59E0B", fontWeight: 500 }}>
                <Flame style={{ width: 13, height: 13 }} fill="currentColor" />
                {user?.streak ?? 0}d
              </span>
              <span style={{ width: 1, height: 12, background: "var(--color-border-tertiary)" }} />
              <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#4F46E5", fontWeight: 500 }}>
                <Star style={{ width: 13, height: 13 }} fill="currentColor" />
                {(user?.xp ?? 0).toLocaleString()} XP
              </span>
            </div>
            <button style={{
              padding: 6, borderRadius: 8,
              background: "none", border: "none", cursor: "pointer",
              color: "var(--color-text-tertiary)", position: "relative",
            }}>
              <Bell style={{ width: 18, height: 18 }} />
            </button>
          </div>
        </header>

        <div style={{ flex: 1, overflowY: "auto" }}>{children}</div>
      </main>

      {toast && <XPToast xp={toast} onDone={() => {}} />}
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────────
function Dashboard({ setPage, user }) {
  const [resources, setResources] = useState([]);
  const [heatmap, setHeatmap]     = useState({});

  useEffect(() => {
    api.resources().then(setResources).catch(console.error);
    api.heatmap().then(setHeatmap).catch(console.error);
  }, []);

  const inProgress = resources.filter(r => r.status === "in-progress");
  const xpPct = user ? Math.round((user.xp / ((user.xp || 0) + (user.xp_to_next || 968))) * 100) : 0;

  const platformTotals = inProgress.reduce((acc, r) => {
    acc[r.platform] = acc[r.platform]
      ? Math.round((acc[r.platform] + r.progress) / 2)
      : r.progress;
    return acc;
  }, {});

  const platformColors = {
    YouTube: "#E24B4A", Udemy: "#7C3AED", Coursera: "#2563EB",
    freeCodeCamp: "#16A34A", Medium: "#64748B",
  };

  const heatmapCells = Array.from({ length: 84 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (83 - i));
    const key = d.toISOString().slice(0, 10);
    const mins = heatmap[key] ?? 0;
    return mins === 0 ? 0 : mins < 20 ? 1 : mins < 45 ? 2 : 3;
  });

  const firstName = user?.name?.split(" ")[0] ?? "there";

  const card = (v, label, sub) => (
    <div key={label} style={{
      background: "var(--color-background-primary)",
      border: "0.5px solid var(--color-border-tertiary)",
      borderRadius: "var(--border-radius-lg)", padding: "16px",
    }}>
      <p style={{ margin: "0 0 3px", fontSize: 22, fontWeight: 500 }}>{v}</p>
      <p style={{ margin: "0 0 2px", fontSize: 12, fontWeight: 500, color: "var(--color-text-secondary)" }}>{label}</p>
      <p style={{ margin: 0, fontSize: 11, color: "var(--color-text-tertiary)" }}>{sub}</p>
    </div>
  );

  return (
    <div style={{ padding: "24px", maxWidth: 960, margin: "0 auto" }}>
      {/* Hero */}
      <div style={{
        background: "linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4c1d95 100%)",
        borderRadius: "var(--border-radius-lg)", padding: "28px 32px", marginBottom: 20, color: "white",
      }}>
        <h1 style={{ margin: "0 0 4px", fontSize: 22, fontWeight: 500 }}>
          Good morning, {firstName}! 👋
        </h1>
        <p style={{ margin: "0 0 20px", opacity: 0.7, fontSize: 13 }}>
          {inProgress.length} course{inProgress.length !== 1 ? "s" : ""} in progress.
        </p>
        <div style={{ maxWidth: 320 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, opacity: 0.7, marginBottom: 5 }}>
            <span>Level {user?.level ?? 1}</span>
            <span>{(user?.xp ?? 0).toLocaleString()} / {((user?.xp ?? 0) + (user?.xp_to_next ?? 968)).toLocaleString()} XP</span>
          </div>
          <div style={{ height: 7, background: "rgba(255,255,255,0.2)", borderRadius: 8, overflow: "hidden" }}>
            <div style={{ width: `${xpPct}%`, height: "100%", background: "rgba(255,255,255,0.9)", borderRadius: 8, transition: "width 0.5s" }} />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {card(inProgress.length, "Courses active", "in progress")}
        {card(resources.filter(r => r.status === "completed").length, "Completed", "resources")}
        {card(`${user?.streak ?? 0}d`, "Streak", "keep it up!")}
        {card(user?.level ?? 1, "Level", "current level")}
      </div>

      {/* Heatmap + Platform */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 16 }}>
        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)", padding: "18px",
        }}>
          <p style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 500 }}>Activity — last 12 weeks</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 3 }}>
            {heatmapCells.map((v, i) => (
              <div key={i} style={{
                aspectRatio: "1", borderRadius: 2,
                background: v === 0 ? "var(--color-background-secondary)" : v === 1 ? "#C7D2FE" : v === 2 ? "#818CF8" : "#4338CA",
              }} />
            ))}
          </div>
        </div>

        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)", padding: "18px",
        }}>
          <p style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 500 }}>Platform progress</p>
          {Object.keys(platformTotals).length === 0
            ? <p style={{ fontSize: 12, color: "var(--color-text-tertiary)" }}>No resources yet.</p>
            : Object.entries(platformTotals).map(([p, pct]) => (
              <div key={p} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                  <span style={{ color: "var(--color-text-secondary)", fontWeight: 500 }}>{p}</span>
                  <span style={{ color: "var(--color-text-tertiary)" }}>{pct}%</span>
                </div>
                <div style={{ height: 5, background: "var(--color-background-secondary)", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ width: `${pct}%`, height: "100%", background: platformColors[p] ?? "#4F46E5", borderRadius: 4 }} />
                </div>
              </div>
            ))
          }
        </div>
      </div>

      {/* Quick actions */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        {[
          { label: "My learning",   page: "my-learning",     emoji: "📚" },
          { label: "Recommended",   page: "recommendations", emoji: "✨" },
          { label: "Analytics",     page: "analytics",       emoji: "📊" },
        ].map(({ label, page, emoji }) => (
          <button key={page} onClick={() => setPage(page)} style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
            padding: "16px", borderRadius: "var(--border-radius-lg)",
            border: "0.5px solid var(--color-border-tertiary)",
            background: "var(--color-background-primary)",
            cursor: "pointer", transition: "all 0.15s", fontSize: 13, fontWeight: 500,
            color: "var(--color-text-secondary)",
          }}>
            <span style={{ fontSize: 22 }}>{emoji}</span>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Auth Layout ────────────────────────────────────────────────────────────────
function AuthLayout({ children }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", background: "var(--color-background-primary)" }}>
      <div style={{
        width: "45%", background: "#0f0e17", display: "flex", flexDirection: "column",
        justifyContent: "space-between", padding: "48px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 9,
            background: "linear-gradient(135deg, #4F46E5, #7C3AED)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Zap style={{ width: 16, height: 16, color: "white" }} fill="white" />
          </div>
          <span style={{ fontSize: 20, fontWeight: 700, color: "white" }}>SkillOS</span>
        </div>
        <div style={{ marginBottom: 80 }}>
          <h1 style={{
            fontSize: 44, fontWeight: 700, color: "white", lineHeight: 1.15, margin: "0 0 16px",
          }}>
            Upgrade your<br />
            <span style={{
              background: "linear-gradient(90deg, #818CF8, #A78BFA)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>
              human potential.
            </span>
          </h1>
          <p style={{ fontSize: 16, color: "rgba(255,255,255,0.5)", maxWidth: 360, lineHeight: 1.6, margin: 0 }}>
            The unified operating system for self-directed learners.
          </p>
        </div>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)" }}>© 2026 SkillOS</p>
      </div>
      <div style={{
        flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "48px",
      }}>
        <div style={{ width: "100%", maxWidth: 400 }}>{children}</div>
      </div>
    </div>
  );
}

// ── Login ──────────────────────────────────────────────────────────────────────
function Login({ onLogin, onGoRegister }) {
  const [showPw, setShowPw] = useState(false);
  const [email, setEmail]   = useState("");
  const [pw, setPw]         = useState("");
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      const data = await api.login(email, pw);
      localStorage.setItem("skillos_token", data.access_token);
      onLogin();
    } catch { setError("Invalid email or password."); }
    finally { setLoading(false); }
  }

  const inp = {
    width: "100%", padding: "10px 12px 10px 36px", fontSize: 13,
    border: "0.5px solid var(--color-border-secondary)",
    borderRadius: "var(--border-radius-md)",
    background: "var(--color-background-secondary)",
    color: "var(--color-text-primary)", outline: "none",
  };

  return (
    <AuthLayout>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ margin: "0 0 6px", fontSize: 24, fontWeight: 500 }}>Welcome back</h2>
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-secondary)" }}>
          Sign in to continue your learning journey.
        </p>
      </div>
      {error && (
        <div style={{
          marginBottom: 16, padding: "10px 14px", borderRadius: "var(--border-radius-md)",
          background: "var(--color-background-danger)", color: "var(--color-text-danger)", fontSize: 13,
          border: "0.5px solid var(--color-border-danger)",
        }}>{error}</div>
      )}
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6, color: "var(--color-text-secondary)" }}>Email</label>
          <div style={{ position: "relative" }}>
            <Mail style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--color-text-tertiary)" }} />
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="you@example.com" style={inp} />
          </div>
        </div>
        <div>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6, color: "var(--color-text-secondary)" }}>Password</label>
          <div style={{ position: "relative" }}>
            <Lock style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--color-text-tertiary)" }} />
            <input type={showPw ? "text" : "password"} value={pw} onChange={e => setPw(e.target.value)} required placeholder="••••••••" style={{ ...inp, paddingRight: 36 }} />
            <button type="button" onClick={() => setShowPw(p => !p)} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--color-text-tertiary)", padding: 0 }}>
              {showPw ? <EyeOff style={{ width: 14, height: 14 }} /> : <Eye style={{ width: 14, height: 14 }} />}
            </button>
          </div>
        </div>
        <button type="submit" disabled={loading} style={{
          width: "100%", padding: "11px", background: "#0f0e17", color: "white",
          border: "none", borderRadius: "var(--border-radius-md)", fontSize: 13, fontWeight: 500,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          opacity: loading ? 0.6 : 1,
        }}>
          {loading ? "Signing in…" : <><span>Sign in</span><ArrowRight style={{ width: 14, height: 14 }} /></>}
        </button>
      </form>
      <p style={{ marginTop: 24, textAlign: "center", fontSize: 13, color: "var(--color-text-secondary)" }}>
        No account?{" "}
        <button onClick={onGoRegister} style={{ background: "none", border: "none", cursor: "pointer", color: "#4F46E5", fontWeight: 500, fontSize: 13, padding: 0 }}>
          Create one for free
        </button>
      </p>
    </AuthLayout>
  );
}

// ── Register ───────────────────────────────────────────────────────────────────
function Register({ onLogin, onGoLogin }) {
  const [showPw, setShowPw]       = useState(false);
  const [name, setName]           = useState("");
  const [email, setEmail]         = useState("");
  const [pw, setPw]               = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [error, setError]         = useState("");
  const [loading, setLoading]     = useState(false);

  async function handleSubmit(e) {
    e.preventDefault(); setError("");
    if (pw !== pwConfirm) { setError("Passwords do not match."); return; }
    if (pw.length < 6) { setError("Password must be at least 6 characters."); return; }
    setLoading(true);
    try {
      const data = await api.register(name, email, pw);
      localStorage.setItem("skillos_token", data.access_token);
      onLogin();
    } catch (err) {
      setError(err.message?.includes("already registered") ? "That email is already registered." : "Something went wrong. Please try again.");
    } finally { setLoading(false); }
  }

  const inp = {
    width: "100%", padding: "10px 12px 10px 36px", fontSize: 13,
    border: "0.5px solid var(--color-border-secondary)",
    borderRadius: "var(--border-radius-md)",
    background: "var(--color-background-secondary)",
    color: "var(--color-text-primary)", outline: "none",
  };

  return (
    <AuthLayout>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ margin: "0 0 6px", fontSize: 24, fontWeight: 500 }}>Create your account</h2>
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-secondary)" }}>Start your learning journey today — it's free.</p>
      </div>
      {error && (
        <div style={{ marginBottom: 16, padding: "10px 14px", borderRadius: "var(--border-radius-md)", background: "var(--color-background-danger)", color: "var(--color-text-danger)", fontSize: 13 }}>{error}</div>
      )}
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {[
          { label: "Full name", type: "text", val: name, set: setName, ph: "Jane Smith", Icon: User },
          { label: "Email",     type: "email", val: email, set: setEmail, ph: "you@example.com", Icon: Mail },
        ].map(({ label, type, val, set, ph, Icon: I }) => (
          <div key={label}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 5, color: "var(--color-text-secondary)" }}>{label}</label>
            <div style={{ position: "relative" }}>
              <I style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--color-text-tertiary)" }} />
              <input type={type} value={val} onChange={e => set(e.target.value)} required placeholder={ph} style={inp} />
            </div>
          </div>
        ))}
        {[
          { label: "Password", val: pw, set: setPw, ph: "Min. 6 characters" },
          { label: "Confirm password", val: pwConfirm, set: setPwConfirm, ph: "Re-enter password" },
        ].map(({ label, val, set, ph }) => (
          <div key={label}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 5, color: "var(--color-text-secondary)" }}>{label}</label>
            <div style={{ position: "relative" }}>
              <Lock style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--color-text-tertiary)" }} />
              <input type={showPw ? "text" : "password"} value={val} onChange={e => set(e.target.value)} required placeholder={ph}
                style={{ ...inp, paddingRight: 36, borderColor: (label.includes("Confirm") && pwConfirm && pw !== pwConfirm) ? "var(--color-border-danger)" : undefined }} />
              {label === "Password" && (
                <button type="button" onClick={() => setShowPw(p => !p)} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--color-text-tertiary)", padding: 0 }}>
                  {showPw ? <EyeOff style={{ width: 14, height: 14 }} /> : <Eye style={{ width: 14, height: 14 }} />}
                </button>
              )}
            </div>
          </div>
        ))}
        <button type="submit" disabled={loading} style={{
          width: "100%", padding: "11px", background: "#4F46E5", color: "white",
          border: "none", borderRadius: "var(--border-radius-md)", fontSize: 13, fontWeight: 500,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          opacity: loading ? 0.6 : 1, marginTop: 4,
        }}>
          {loading ? "Creating…" : <><span>Create account</span><ArrowRight style={{ width: 14, height: 14 }} /></>}
        </button>
      </form>
      <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "var(--color-text-secondary)" }}>
        Already have an account?{" "}
        <button onClick={onGoLogin} style={{ background: "none", border: "none", cursor: "pointer", color: "#4F46E5", fontWeight: 500, fontSize: 13, padding: 0 }}>
          Sign in
        </button>
      </p>
    </AuthLayout>
  );
}

// ── Root App ───────────────────────────────────────────────────────────────────
export default function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("skillos_token"));
  const [authPage, setAuthPage] = useState("login");
  const [user, setUser]         = useState(null);
  const [page, setPage]         = useState("dashboard");
  const [toast, setToast]       = useState(null);

  const refreshUser = useCallback(() => {
    api.me().then(setUser).catch(() => {
      localStorage.removeItem("skillos_token");
      setLoggedIn(false);
    });
  }, []);

  useEffect(() => {
    if (loggedIn) refreshUser();
  }, [loggedIn, refreshUser]);

  function handleLogin() { setLoggedIn(true); setAuthPage("login"); }
  function handleLogout() {
    localStorage.removeItem("skillos_token");
    setLoggedIn(false); setUser(null); setPage("dashboard");
  }

  if (!loggedIn) {
    return authPage === "register"
      ? <Register onLogin={handleLogin} onGoLogin={() => setAuthPage("login")} />
      : <Login    onLogin={handleLogin} onGoRegister={() => setAuthPage("register")} />;
  }

  const pageEl = {
    "dashboard":       <Dashboard setPage={setPage} user={user} />,
    "my-learning":     <MyLearning onXP={() => refreshUser()} />,
    "recommendations": <Recommendations />,
    "flashcards":      <Flashcards onXP={() => refreshUser()} />,
    "buddies":         <StudyBuddies />,
    "analytics":       <Analytics />,
    "rewards":         <Rewards user={user} />,
  }[page] ?? <Dashboard setPage={setPage} user={user} />;

  return (
    <Shell page={page} setPage={setPage} onLogout={handleLogout} user={user} toast={toast}>
      {pageEl}
    </Shell>
  );
}
