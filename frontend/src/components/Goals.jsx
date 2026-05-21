import React, { useState, useEffect } from "react";
import { Target, Plus } from "lucide-react";
import { api } from "../api";
import GoalWizard from "./GoalWizard";
import GoalProgress from "./GoalProgress";

export default function Goals() {
  const [goals, setGoals] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [showWizard, setShowWizard] = useState(false);
  const [loading, setLoading] = useState(true);

  function loadGoals() {
    setLoading(true);
    api.listGoals()
      .then((data) => {
        setGoals(data);
        if (data.length && !selectedId) setSelectedId(data[0].id);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadGoals();
  }, []);

  if (showWizard) {
    return (
      <GoalWizard
        onComplete={() => {
          setShowWizard(false);
          loadGoals();
        }}
      />
    );
  }

  const selected = goals.find((g) => g.id === selectedId);

  return (
    <div className="p-8 max-w-4xl mx-auto w-full">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Learning goals</h2>
          <p className="text-sm text-slate-500">AI-generated paths with skill-gap analysis</p>
        </div>
        <button
          onClick={() => setShowWizard(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4" /> New goal
        </button>
      </div>

      {loading && <p className="text-sm text-slate-400">Loading…</p>}

      {!loading && goals.length === 0 && (
        <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-2xl">
          <Target className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500 mb-4">No goals yet. Create one to get a personalized path.</p>
          <button onClick={() => setShowWizard(true)} className="text-indigo-600 font-semibold text-sm">
            Start goal wizard →
          </button>
        </div>
      )}

      {goals.length > 0 && (
        <>
          <div className="flex flex-wrap gap-2 mb-6">
            {goals.map((g) => (
              <button
                key={g.id}
                onClick={() => setSelectedId(g.id)}
                className={`px-4 py-2 rounded-xl text-sm font-medium border transition-colors ${
                  selectedId === g.id
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-slate-700 border-slate-200 hover:border-indigo-300"
                }`}
              >
                {g.title}
              </button>
            ))}
          </div>

          {selected && (
            <>
              <div className="bg-white border border-slate-200 rounded-2xl p-6 mb-6">
                <h3 className="font-bold text-slate-900 mb-2">{selected.title}</h3>
                <p className="text-sm text-slate-500 mb-4">{selected.description || selected.category}</p>
                {selected.milestones?.length > 0 && (
                  <ol className="space-y-2">
                    {selected.milestones.map((m, i) => (
                      <li key={m.id || i} className="text-sm text-slate-700 flex gap-2">
                        <span className="text-indigo-600 font-bold">{m.sequence || i + 1}.</span>
                        <span>
                          {m.milestone_title} — {m.target_duration_hours}h
                          <span className="text-slate-400 ml-1">({m.status})</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
              <GoalProgress goalId={selected.id} />
            </>
          )}
        </>
      )}
    </div>
  );
}
