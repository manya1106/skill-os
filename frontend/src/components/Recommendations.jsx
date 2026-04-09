import React, { useState, useEffect } from "react";
import { Sparkles, ThumbsDown, Plus, Clock, Zap, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { PlatformBadge } from "./ui";
import { api } from "../api";

export default function Recommendations() {
  const [recs, setRecs]           = useState([]);
  const [struggles, setStruggles] = useState([]);
  const [model, setModel]         = useState("");
  const [loading, setLoading]     = useState(true);
  const [dismissed, setDismissed] = useState(new Set());
  const [saved, setSaved]         = useState(new Set());
  const [showStruggles, setShowStruggles] = useState(true);

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

  function dismiss(id)    { setDismissed(prev => new Set([...prev, id])); }
  function toggleSave(id) {
    setSaved(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const scoreColor = s =>
    s >= 90 ? "text-green-600 bg-green-50" :
    s >= 80 ? "text-indigo-600 bg-indigo-50" :
              "text-amber-600 bg-amber-50";

  return (
    <div className="p-8 max-w-5xl mx-auto w-full">
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-2xl p-6 mb-6 flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shrink-0">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1">
          <p className="font-bold text-slate-900 mb-1">Personalised for you</p>
          <p className="text-sm text-slate-500">
            Recommendations based on your learning history and goals.
          </p>
        </div>
        {model && (
          <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-indigo-100 text-indigo-700 shrink-0 self-start">
            {model === "dae_cf" ? "DAE-CF model" : model === "tfidf" ? "TF-IDF model" : "curated"}
          </span>
        )}
      </div>

      {struggles.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 mb-6">
          <button
            onClick={() => setShowStruggles(s => !s)}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
              <p className="font-bold text-amber-900 text-sm">
                Struggling with {struggles.length} resource{struggles.length > 1 ? "s" : ""}
              </p>
            </div>
            {showStruggles ? <ChevronUp className="w-4 h-4 text-amber-600" /> : <ChevronDown className="w-4 h-4 text-amber-600" />}
          </button>
          {showStruggles && (
            <div className="mt-4 space-y-3">
              {struggles.map(s => (
                <div key={s.resource_id} className="bg-white rounded-xl p-4 border border-amber-100">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-semibold text-slate-900 truncate">{s.title}</p>
                    <span className="text-xs font-bold text-amber-700 ml-2 shrink-0">
                      {Math.round(s.struggle_score * 100)}%
                    </span>
                  </div>
                  {(s.interventions ?? []).map((tip, i) => (
                    <p key={i} className="text-xs text-slate-500 flex gap-1.5">
                      <span className="text-amber-500 shrink-0">→</span>{tip}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="bg-white border border-slate-200 rounded-2xl p-5 animate-pulse">
              <div className="h-3 bg-slate-200 rounded w-1/3 mb-3" />
              <div className="h-4 bg-slate-200 rounded w-full mb-2" />
              <div className="h-3 bg-slate-200 rounded w-2/3" />
            </div>
          ))}
        </div>
      )}

      {!loading && visible.length === 0 && (
        <div className="text-center py-20 text-slate-400">
          <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="font-semibold">All caught up!</p>
          <p className="text-sm mt-1">Check back later for fresh recommendations.</p>
        </div>
      )}

      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {visible.map(rec => (
            <RecCard key={rec.id} rec={rec}
              isSaved={saved.has(rec.id)}
              onSave={() => toggleSave(rec.id)}
              onDismiss={() => dismiss(rec.id)}
              scoreColor={scoreColor(rec.match_score)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RecCard({ rec, isSaved, onSave, onDismiss, scoreColor }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <PlatformBadge platform={rec.platform} />
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${scoreColor}`}>
          {rec.match_score}% match
        </span>
      </div>
      <p className="font-semibold text-slate-900 text-sm leading-snug">{rec.title}</p>
      <div className="flex items-center gap-2 flex-wrap">
        {rec.duration && (
          <span className="flex items-center gap-1 text-xs text-slate-500">
            <Clock className="w-3.5 h-3.5" /> {rec.duration}
          </span>
        )}
        {(rec.tags ?? []).map(t => (
          <span key={t} className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full">{t}</span>
        ))}
      </div>
      {rec.reason && (
        <p className="text-xs text-indigo-500 font-medium flex items-center gap-1">
          <Zap className="w-3 h-3" /> {rec.reason}
        </p>
      )}
      <div className="flex gap-2 mt-auto pt-2 border-t border-slate-100">
        <button onClick={onSave}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-semibold border transition-all ${
            isSaved ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-slate-700 border-slate-200 hover:border-indigo-300 hover:text-indigo-600"
          }`}>
          <Plus className="w-3.5 h-3.5" />{isSaved ? "Saved" : "Save"}
        </button>
        <button onClick={onDismiss}
          className="p-2 rounded-xl border border-slate-200 text-slate-400 hover:text-red-500 hover:border-red-200 transition-all">
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}