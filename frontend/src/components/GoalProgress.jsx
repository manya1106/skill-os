import React, { useState, useEffect } from "react";
import { TrendingUp, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "../api";

export default function GoalProgress({ goalId }) {
  const [pred, setPred] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/analytics/predictions/${goalId}`)
      .then(setPred)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [goalId]);

  if (loading || !pred) return <div className="p-4 text-sm text-slate-400">Loading predictions…</div>;

  const probColor = pred.completion_probability_pct >= 70 ? "green" :
                    pred.completion_probability_pct >= 40 ? "amber" : "red";

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Completion Probability Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-sm text-slate-500 mb-1">Completion Probability</p>
            <p className={`text-3xl font-bold ${
              probColor === "green" ? "text-green-600" :
              probColor === "amber" ? "text-amber-600" : "text-red-600"
            }`}>
              {pred.completion_probability_pct}%
            </p>
          </div>
          {pred.completion_probability_pct >= 70
            ? <CheckCircle2 className="w-8 h-8 text-green-500" />
            : <AlertCircle className="w-8 h-8 text-amber-500" />
          }
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          Based on your study pace of {pred.avg_hours_per_week} hrs/week,
          you're {pred.on_track ? "on track" : "behind schedule"}.
        </p>
      </div>

      {/* Timeline Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6">
        <div className="mb-4">
          <p className="text-sm text-slate-500 mb-1">Projected Completion</p>
          <p className="text-2xl font-bold text-slate-900">
            {pred.projected_completion_date
              ? new Date(pred.projected_completion_date).toLocaleDateString("en-IN", {
                month: "short", day: "numeric", year: "numeric"
              })
              : "—"
            }
          </p>
        </div>
        {pred.deadline && (
          <p className={`text-xs font-medium ${
            pred.on_track ? "text-green-600" : "text-red-600"
          }`}>
            Deadline: {new Date(pred.deadline).toLocaleDateString("en-IN")}
          </p>
        )}
      </div>

      {/* Study Schedule Card */}
      <div className="md:col-span-2 bg-slate-50 border border-slate-200 rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <TrendingUp className="w-6 h-6 text-indigo-600 mt-1 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="font-semibold text-slate-900 mb-2">Recommended Study Schedule</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-500 text-xs mb-1">Per day</p>
                <p className="text-lg font-bold text-slate-900">{pred.recommended_daily_minutes} min</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Weeks remaining</p>
                <p className="text-lg font-bold text-slate-900">
                  {pred.weeks_needed ? Math.ceil(pred.weeks_needed) : "—"}
                </p>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-3 leading-relaxed">
              {pred.recommended_daily_minutes} minutes daily will help you complete {pred.milestones_completed}/{pred.milestones_total} milestones on time.
            </p>
          </div>
        </div>
      </div>

      {/* Milestone Progress */}
      <div className="md:col-span-2 bg-white border border-slate-200 rounded-2xl p-6">
        <h3 className="font-semibold text-slate-900 mb-4">Progress</h3>
        <div className="flex items-center gap-4">
          <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-600 transition-all"
              style={{
                width: `${(pred.milestones_completed / pred.milestones_total) * 100}%`
              }}
            />
          </div>
          <span className="text-sm font-semibold text-slate-700">
            {pred.milestones_completed}/{pred.milestones_total}
          </span>
        </div>
      </div>
    </div>
  );
}