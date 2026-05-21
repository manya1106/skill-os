import React, { useState } from "react";
import { ChevronRight, ChevronLeft, CheckCircle2 } from "lucide-react";
import { api } from "../api";

const GOAL_CATEGORIES = [
  { id: "web-dev", label: "Web Development", emoji: "🌐" },
  { id: "data-sci", label: "Data Science", emoji: "📊" },
  { id: "ml", label: "Machine Learning", emoji: "🤖" },
  { id: "career", label: "Career Switch", emoji: "🎯" },
  { id: "other", label: "Custom Goal", emoji: "✨" },
];

const LEARNING_STYLES = [
  { id: "visual", label: "Visual", desc: "Videos, diagrams, visual examples" },
  { id: "auditory", label: "Auditory", desc: "Podcasts, lectures, discussions" },
  { id: "kinesthetic", label: "Kinesthetic", desc: "Hands-on projects, coding" },
  { id: "reading", label: "Reading/Writing", desc: "Books, articles, notes" },
];

const PACE_OPTIONS = [
  { id: "slow", label: "Slow & Steady", desc: "5 hrs/week, 6+ months" },
  { id: "moderate", label: "Moderate", desc: "10 hrs/week, 3-6 months" },
  { id: "fast", label: "Accelerated", desc: "20+ hrs/week, 6-12 weeks" },
];

export default function GoalWizard({ onComplete }) {
  const [step, setStep] = useState(1); // 1-5
  const [goal, setGoal] = useState({
    title: "",
    description: "",
    category: "",
    target_level: 1,
    deadline: null,
  });
  const [prefs, setPrefs] = useState({
    study_hours_per_week: 10,
    preferred_platforms: ["YouTube", "Udemy", "Coursera"],
    learning_style: "visual",
    pace: "moderate",
    preferred_interaction_mode: "collaborative",
  });
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setLoading(true);
    try {
      // Create goal
      const goalRes = await api.createGoal({
        ...goal,
        description: goal.description || `Learn ${goal.title}`,
      });
      await api.updatePreferences({
        ...prefs,
        preferred_interaction_mode: prefs.preferred_interaction_mode || "collaborative",
      });
      
      onComplete(goalRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const stepContent = {
    1: <Step1_Welcome />,
    2: <Step2_GoalDetails goal={goal} setGoal={setGoal} />,
    3: <Step3_LearningStyle prefs={prefs} setPrefs={setPrefs} />,
    4: <Step4_Schedule prefs={prefs} setPrefs={setPrefs} />,
    5: <Step5_Review goal={goal} prefs={prefs} />,
  };

  return (
    <div style={{
      maxWidth: 640, margin: "0 auto", padding: "2rem",
    }}>
      <div style={{ marginBottom: "2rem" }}>
        <div style={{
          height: 6, background: "var(--color-background-secondary)",
          borderRadius: 3, overflow: "hidden",
        }}>
          <div style={{
            width: `${(step / 5) * 100}%`, height: "100%",
            background: "#4F46E5", transition: "width 0.3s",
          }} />
        </div>
        <p style={{
          marginTop: 8, fontSize: 12, color: "var(--color-text-tertiary)",
        }}>
          Step {step} of 5
        </p>
      </div>

      <div style={{ minHeight: 300, marginBottom: "2rem" }}>
        {stepContent[step]}
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
        <button onClick={() => setStep(s => Math.max(1, s - 1))}
          disabled={step === 1}
          style={{
            padding: "10px 16px", border: "0.5px solid var(--color-border-secondary)",
            borderRadius: 10, fontSize: 13, fontWeight: 500,
            background: "transparent", cursor: step === 1 ? "not-allowed" : "pointer",
            opacity: step === 1 ? 0.5 : 1,
          }}>
          <ChevronLeft style={{ width: 14, height: 14, marginRight: 4, display: "inline" }} />
          Back
        </button>

        <button onClick={step === 5 ? handleSubmit : () => setStep(s => s + 1)}
          disabled={loading}
          style={{
            padding: "10px 20px", background: "#4F46E5", color: "white",
            border: "none", borderRadius: 10, fontSize: 13, fontWeight: 500,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.6 : 1,
          }}>
          {step === 5 ? "Complete" : "Next"}
          {step < 5 && <ChevronRight style={{ width: 14, height: 14, marginLeft: 4, display: "inline" }} />}
        </button>
      </div>
    </div>
  );
}

// Step components
function Step1_Welcome() {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🎯</div>
      <h2 style={{ fontSize: 20, fontWeight: 500, marginBottom: 8 }}>
        Define Your Learning Goal
      </h2>
      <p style={{ color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
        Let's set up a personalized learning path. This wizard will help you create structured milestones and identify resources tailored to your pace and style.
      </p>
    </div>
  );
}

function Step2_GoalDetails({ goal, setGoal }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 500, marginBottom: 16 }}>
        What do you want to learn?
      </h2>
      
      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
        Goal Title *
      </label>
      <input type="text" placeholder="e.g., Master React & Node.js"
        value={goal.title}
        onChange={e => setGoal({...goal, title: e.target.value})}
        style={{
          width: "100%", padding: "10px 12px", border: "0.5px solid var(--color-border-secondary)",
          borderRadius: 10, fontSize: 13, marginBottom: 16, fontFamily: "inherit",
        }} />

      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
        Category
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 16 }}>
        {GOAL_CATEGORIES.slice(0, 4).map(cat => (
          <button key={cat.id} onClick={() => setGoal({...goal, category: cat.id})}
            style={{
              padding: 12, borderRadius: 10,
              border: `2px solid ${goal.category === cat.id ? "#4F46E5" : "var(--color-border-secondary)"}`,
              background: goal.category === cat.id ? "#EEF2FF" : "white",
              fontSize: 13, cursor: "pointer", fontWeight: 500,
            }}>
            <div style={{ fontSize: 20, marginBottom: 4 }}>{cat.emoji}</div>
            {cat.label}
          </button>
        ))}
      </div>

      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
        Proficiency Target
      </label>
      <select value={goal.target_level}
        onChange={e => setGoal({...goal, target_level: parseInt(e.target.value)})}
        style={{
          width: "100%", padding: "10px 12px", border: "0.5px solid var(--color-border-secondary)",
          borderRadius: 10, fontSize: 13, fontFamily: "inherit",
        }}>
        <option value={1}>Beginner</option>
        <option value={2}>Intermediate</option>
        <option value={3}>Advanced</option>
        <option value={4}>Expert</option>
      </select>
    </div>
  );
}

const INTERACTION_MODES = [
  { id: "teaching", label: "Mutual teaching", desc: "Take turns explaining concepts" },
  { id: "collaborative", label: "Collaborative", desc: "Solve problems together" },
  { id: "discussion", label: "Discussion", desc: "Debate ideas and quiz each other" },
];

function Step3_LearningStyle({ prefs, setPrefs }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 500, marginBottom: 16 }}>
        How do you learn best?
      </h2>
      <div style={{ display: "grid", gap: 10, marginBottom: 20 }}>
        {LEARNING_STYLES.map(style => (
          <button key={style.id} onClick={() => setPrefs({...prefs, learning_style: style.id})}
            style={{
              padding: 12, borderRadius: 10, textAlign: "left",
              border: `2px solid ${prefs.learning_style === style.id ? "#4F46E5" : "var(--color-border-secondary)"}`,
              background: prefs.learning_style === style.id ? "#EEF2FF" : "white",
              cursor: "pointer",
            }}>
            <p style={{ margin: "0 0 4px", fontSize: 13, fontWeight: 500 }}>{style.label}</p>
            <p style={{ margin: 0, fontSize: 11, color: "var(--color-text-secondary)" }}>
              {style.desc}
            </p>
          </button>
        ))}
      </div>
      <h2 style={{ fontSize: 14, fontWeight: 500, marginBottom: 10 }}>
        Preferred buddy interaction mode
      </h2>
      <div style={{ display: "grid", gap: 8 }}>
        {INTERACTION_MODES.map(m => (
          <button key={m.id} onClick={() => setPrefs({ ...prefs, preferred_interaction_mode: m.id })}
            style={{
              padding: 10, borderRadius: 10, textAlign: "left",
              border: `2px solid ${prefs.preferred_interaction_mode === m.id ? "#4F46E5" : "var(--color-border-secondary)"}`,
              background: prefs.preferred_interaction_mode === m.id ? "#EEF2FF" : "white",
              cursor: "pointer", fontSize: 12,
            }}>
            <strong>{m.label}</strong> — {m.desc}
          </button>
        ))}
      </div>
    </div>
  );
}

function Step4_Schedule({ prefs, setPrefs }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 500, marginBottom: 16 }}>
        How much time can you commit?
      </h2>
      <div style={{ display: "grid", gap: 10, marginBottom: 20 }}>
        {PACE_OPTIONS.map(pace => (
          <button key={pace.id} onClick={() => setPrefs({...prefs, pace: pace.id})}
            style={{
              padding: 12, borderRadius: 10, textAlign: "left",
              border: `2px solid ${prefs.pace === pace.id ? "#4F46E5" : "var(--color-border-secondary)"}`,
              background: prefs.pace === pace.id ? "#EEF2FF" : "white",
              cursor: "pointer",
            }}>
            <p style={{ margin: "0 0 4px", fontSize: 13, fontWeight: 500 }}>{pace.label}</p>
            <p style={{ margin: 0, fontSize: 11, color: "var(--color-text-secondary)" }}>
              {pace.desc}
            </p>
          </button>
        ))}
      </div>

      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
        Preferred Platforms
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
        {["YouTube", "Udemy", "Coursera", "freeCodeCamp", "Medium"].map(p => (
          <label key={p} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            <input type="checkbox"
              checked={prefs.preferred_platforms.includes(p)}
              onChange={e => setPrefs({
                ...prefs,
                preferred_platforms: e.target.checked
                  ? [...prefs.preferred_platforms, p]
                  : prefs.preferred_platforms.filter(x => x !== p)
              })}
              style={{ cursor: "pointer" }} />
            <span style={{ fontSize: 12 }}>{p}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function Step5_Review({ goal, prefs }) {
  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 500, marginBottom: 16 }}>
        Ready to start?
      </h2>
      <div style={{
        background: "var(--color-background-secondary)",
        borderRadius: 10, padding: 16, marginBottom: 16,
      }}>
        <h3 style={{ fontSize: 13, fontWeight: 500, margin: "0 0 8px" }}>
          {goal.title}
        </h3>
        <p style={{
          margin: "0 0 12px", fontSize: 12, color: "var(--color-text-secondary)",
        }}>
          {goal.description}
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 11 }}>
          <div>
            <span style={{ color: "var(--color-text-tertiary)" }}>Category:</span>
            <p style={{ margin: 0, fontWeight: 500 }}>{goal.category}</p>
          </div>
          <div>
            <span style={{ color: "var(--color-text-tertiary)" }}>Target Level:</span>
            <p style={{ margin: 0, fontWeight: 500 }}>
              {["Beginner", "Intermediate", "Advanced", "Expert"][goal.target_level - 1]}
            </p>
          </div>
          <div>
            <span style={{ color: "var(--color-text-tertiary)" }}>Pace:</span>
            <p style={{ margin: 0, fontWeight: 500 }}>{prefs.pace}</p>
          </div>
          <div>
            <span style={{ color: "var(--color-text-tertiary)" }}>Learning Style:</span>
            <p style={{ margin: 0, fontWeight: 500 }}>
              {prefs.learning_style.charAt(0).toUpperCase() + prefs.learning_style.slice(1)}
            </p>
          </div>
        </div>
      </div>

      <div style={{
        background: "#EEF2FF", border: "1px solid #C7D2FE",
        borderRadius: 10, padding: 12, fontSize: 12, color: "#4338CA",
      }}>
        ✨ A personalized learning path with milestones will be generated after you complete this wizard.
      </div>
    </div>
  );
}