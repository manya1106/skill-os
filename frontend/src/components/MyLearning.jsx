import React, { useState, useEffect, useMemo } from "react";
import {
  Plus, ExternalLink, Trash2, CheckCircle2, PlayCircle,
  BookOpen, Search, X, SlidersHorizontal,
} from "lucide-react";
import { PlatformBadge, ProgressBar, EmptyState } from "./ui";
import { api } from "../api";

const PLATFORMS = ["YouTube", "Udemy", "Coursera", "freeCodeCamp", "Medium"];

const STATUS_META = {
  "not-started": { label: "Not started", cls: "bg-slate-100 text-slate-500" },
  "in-progress":  { label: "In progress",  cls: "bg-indigo-50 text-indigo-600" },
  "completed":    { label: "Completed",    cls: "bg-green-50 text-green-600"   },
};

const EMPTY_FORM = { platform: "YouTube", title: "", url: "", duration: "", tags: "" };

// Parse "4h 30min", "90 min", "2h" → minutes
function parseMins(dur) {
  if (!dur) return null;
  const h = (dur.match(/(\d+)\s*h/i) || [])[1] || 0;
  const m = (dur.match(/(\d+)\s*m/i) || [])[1] || 0;
  return parseInt(h) * 60 + parseInt(m);
}

const DURATION_OPTS = [
  { key: "all",    label: "Any length",  test: () => true },
  { key: "short",  label: "< 2h",        test: m => m !== null && m < 120 },
  { key: "medium", label: "2 – 10h",     test: m => m !== null && m >= 120 && m < 600 },
  { key: "long",   label: "10h+",        test: m => m !== null && m >= 600 },
];

const SORT_OPTS = [
  { key: "recent",   label: "Recent" },
  { key: "progress", label: "Progress ↓" },
  { key: "az",       label: "Title A–Z" },
  { key: "duration", label: "Duration ↓" },
];

export default function MyLearning() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState(EMPTY_FORM);
  const [saving, setSaving]       = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Filter state
  const [search, setSearch]           = useState("");
  const [statusF, setStatusF]         = useState("all");
  const [platformF, setPlatformF]     = useState("all");
  const [durationF, setDurationF]     = useState("all");
  const [sortBy, setSortBy]           = useState("recent");
  const [progressMin, setProgressMin] = useState(0);
  const [progressMax, setProgressMax] = useState(100);

  useEffect(() => {
    api.resources().then(setResources).catch(console.error).finally(() => setLoading(false));
  }, []);

  // ── Derived filtered + sorted list ──────────────────────────────────────────
  const filtered = useMemo(() => {
    const durTest = DURATION_OPTS.find(d => d.key === durationF)?.test ?? (() => true);
    const q = search.toLowerCase();

    let list = resources.filter(r => {
      if (statusF !== "all" && r.status !== statusF) return false;
      if (platformF !== "all" && r.platform !== platformF) return false;
      const mins = parseMins(r.duration);
      if (!durTest(mins)) return false;
      const prog = r.progress ?? 0;
      if (prog < progressMin || prog > progressMax) return false;
      if (q) {
        const inTitle = r.title?.toLowerCase().includes(q);
        const inTags  = (r.tags || []).some(t => t.toLowerCase().includes(q));
        const inPlat  = r.platform?.toLowerCase().includes(q);
        if (!inTitle && !inTags && !inPlat) return false;
      }
      return true;
    });

    switch (sortBy) {
      case "progress": list = [...list].sort((a, b) => (b.progress ?? 0) - (a.progress ?? 0)); break;
      case "az":       list = [...list].sort((a, b) => a.title.localeCompare(b.title)); break;
      case "duration": list = [...list].sort((a, b) => (parseMins(b.duration) ?? 0) - (parseMins(a.duration) ?? 0)); break;
      // "recent" — default insertion order
    }
    return list;
  }, [resources, search, statusF, platformF, durationF, sortBy, progressMin, progressMax]);

  const activeCount = [
    search, statusF !== "all", platformF !== "all",
    durationF !== "all", progressMin > 0, progressMax < 100,
  ].filter(Boolean).length;

  function clearAll() {
    setSearch(""); setStatusF("all"); setPlatformF("all");
    setDurationF("all"); setSortBy("recent");
    setProgressMin(0); setProgressMax(100);
  }

  // ── Mutations ────────────────────────────────────────────────────────────────
  async function handleAdd(e) {
    e.preventDefault(); setSaving(true);
    try {
      const payload = {
        platform: form.platform, title: form.title,
        url: form.url || null, duration: form.duration || null,
        tags: form.tags ? form.tags.split(",").map(t => t.trim()).filter(Boolean) : [],
      };
      const created = await api.createResource(payload);
      setResources(prev => [created, ...prev]);
      setForm(EMPTY_FORM); setShowForm(false);
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  }

  async function updateStatus(id, status) {
    try {
      const updated = await api.updateResource(id, { status });
      setResources(prev => prev.map(r => r.id === id ? { ...r, ...updated } : r));
    } catch (err) { console.error(err); }
  }

  async function updateProgress(id, progress) {
    try {
      const updated = await api.updateResource(id, { progress });
      setResources(prev => prev.map(r => r.id === id ? { ...r, ...updated } : r));
    } catch (err) { console.error(err); }
  }

  async function deleteResource(id) {
    try { await api.deleteResource(id); } catch (_) {}
    setResources(prev => prev.filter(r => r.id !== id));
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="p-8 max-w-5xl mx-auto w-full">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">My Learning</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {resources.length} tracked
            {filtered.length !== resources.length && ` · ${filtered.length} shown`}
          </p>
        </div>
        <button onClick={() => setShowForm(f => !f)}
          className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 transition-colors">
          <Plus className="w-4 h-4" /> Add resource
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form onSubmit={handleAdd}
          className="bg-white border border-slate-200 rounded-2xl p-6 mb-6 space-y-4">
          <p className="text-sm font-bold text-slate-900">New resource</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Platform</label>
              <select value={form.platform}
                onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400">
                {PLATFORMS.map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Duration (optional)</label>
              <input type="text" placeholder="e.g. 4h 30min" value={form.duration}
                onChange={e => setForm(f => ({ ...f, duration: e.target.value }))}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
          </div>
          {[
            { label: "Title *", key: "title", type: "text",  ph: "Course or resource title", req: true },
            { label: "URL (optional)", key: "url", type: "url", ph: "https://…", req: false },
            { label: "Tags (comma separated)", key: "tags", type: "text", ph: "Python, ML, React", req: false },
          ].map(({ label, key, type, ph, req }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
              <input type={type} required={req} placeholder={ph} value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
            </div>
          ))}
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving}
              className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-60 transition-colors">
              {saving ? "Saving…" : "Save resource"}
            </button>
            <button type="button" onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
              className="px-5 py-2.5 bg-slate-100 text-slate-700 text-sm font-semibold rounded-xl hover:bg-slate-200 transition-colors">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* ── Search bar ── */}
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <input
          type="text"
          placeholder="Search by title, tag, or platform…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-9 pr-10 py-2.5 text-sm border border-slate-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
        {search && (
          <button onClick={() => setSearch("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* ── Filter chips row ── */}
      <div className="flex flex-wrap gap-2 mb-2">
        {/* Status */}
        {[
          { key: "all", label: "All" },
          { key: "not-started", label: "Not started" },
          { key: "in-progress", label: "In progress" },
          { key: "completed",   label: "Completed" },
        ].map(t => (
          <button key={t.key} onClick={() => setStatusF(t.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
              statusF === t.key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
            }`}>
            {t.label}
          </button>
        ))}

        <span className="self-center text-slate-200 text-lg select-none">|</span>

        {/* Platform */}
        {["all", ...PLATFORMS].map(p => (
          <button key={p} onClick={() => setPlatformF(p)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
              platformF === p
                ? "bg-indigo-600 text-white"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200"
            }`}>
            {p === "all" ? "All platforms" : p === "freeCodeCamp" ? "fCC" : p}
          </button>
        ))}

        {/* Advanced toggle */}
        <button onClick={() => setShowFilters(f => !f)}
          className={`ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
            showFilters || durationF !== "all" || progressMin > 0 || progressMax < 100
              ? "bg-violet-600 text-white"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
          }`}>
          <SlidersHorizontal className="w-3 h-3" />
          Filters{activeCount > 0 ? ` (${activeCount})` : ""}
        </button>
      </div>

      {/* ── Advanced filters panel ── */}
      {showFilters && (
        <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 mb-4 space-y-4">
          {/* Duration */}
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Duration</p>
            <div className="flex flex-wrap gap-2">
              {DURATION_OPTS.map(d => (
                <button key={d.key} onClick={() => setDurationF(d.key)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                    durationF === d.key
                      ? "bg-violet-600 text-white"
                      : "bg-white border border-slate-200 text-slate-500 hover:bg-slate-100"
                  }`}>
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Progress range */}
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">
              Progress: {progressMin}% – {progressMax}%
            </p>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400 w-6">0</span>
              <input type="range" min={0} max={100} step={5}
                value={progressMin}
                onChange={e => setProgressMin(Math.min(Number(e.target.value), progressMax - 5))}
                className="flex-1 accent-violet-600" />
              <input type="range" min={0} max={100} step={5}
                value={progressMax}
                onChange={e => setProgressMax(Math.max(Number(e.target.value), progressMin + 5))}
                className="flex-1 accent-violet-600" />
              <span className="text-xs text-slate-400 w-8">100</span>
            </div>
          </div>

          {/* Sort */}
          <div className="flex items-center gap-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sort by</p>
            <div className="flex flex-wrap gap-2">
              {SORT_OPTS.map(s => (
                <button key={s.key} onClick={() => setSortBy(s.key)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                    sortBy === s.key
                      ? "bg-slate-900 text-white"
                      : "bg-white border border-slate-200 text-slate-500 hover:bg-slate-100"
                  }`}>
                  {s.label}
                </button>
              ))}
            </div>
            {activeCount > 0 && (
              <button onClick={clearAll}
                className="ml-auto text-xs text-red-500 hover:text-red-700 font-medium flex items-center gap-1">
                <X className="w-3 h-3" /> Clear all
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Results summary ── */}
      {!loading && resources.length > 0 && (
        <p className="text-xs text-slate-400 mb-4">
          Showing {filtered.length} of {resources.length} resources
          {activeCount > 0 && (
            <button onClick={clearAll} className="ml-2 text-indigo-500 hover:text-indigo-700">
              Clear filters
            </button>
          )}
        </p>
      )}

      {loading && <p className="text-sm text-slate-400">Loading…</p>}

      {!loading && filtered.length === 0 && (
        <EmptyState
          icon="📚"
          title={resources.length === 0 ? "No resources yet" : "No results"}
          sub={resources.length === 0
            ? "Add your first resource above."
            : "Try broadening your search or filters."}
        />
      )}

      <div className="space-y-4">
        {filtered.map(r => (
          <ResourceCard
            key={r.id}
            resource={r}
            onStatusChange={status => updateStatus(r.id, status)}
            onProgressChange={prog => updateProgress(r.id, prog)}
            onDelete={() => deleteResource(r.id)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Resource card (unchanged logic, stable UI) ──────────────────────────────
function ResourceCard({ resource: r, onStatusChange, onProgressChange, onDelete }) {
  const sm = STATUS_META[r.status] ?? STATUS_META["not-started"];

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start gap-4">
        <div className="shrink-0 mt-0.5">
          {r.status === "completed"
            ? <CheckCircle2 className="w-5 h-5 text-green-500" />
            : r.status === "in-progress"
            ? <PlayCircle className="w-5 h-5 text-indigo-500" />
            : <BookOpen className="w-5 h-5 text-slate-300" />}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <PlatformBadge platform={r.platform} />
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sm.cls}`}>
              {sm.label}
            </span>
          </div>

          <p className="font-semibold text-slate-900 text-sm truncate mb-1">{r.title}</p>

          {r.duration && <p className="text-xs text-slate-400 mb-2">{r.duration}</p>}

          {(r.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {r.tags.map(t => (
                <span key={t} className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full">{t}</span>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3">
            <ProgressBar value={r.progress ?? 0} />
            <span className="text-xs font-bold text-slate-500 w-8 text-right shrink-0">
              {r.progress ?? 0}%
            </span>
          </div>
          <input type="range" min="0" max="100" step="5"
            value={r.progress ?? 0}
            onChange={e => onProgressChange(Number(e.target.value))}
            className="w-full mt-1 accent-indigo-600" />
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0 ml-2">
          {r.url && (
            <a href={r.url} target="_blank" rel="noopener noreferrer"
              className="p-1.5 text-slate-400 hover:text-indigo-600 transition-colors" title="Open resource">
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button onClick={onDelete}
            className="p-1.5 text-slate-300 hover:text-red-500 transition-colors" title="Remove">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex gap-2 mt-4 pt-3 border-t border-slate-100">
        {Object.entries(STATUS_META).map(([key, meta]) => (
          <button key={key} onClick={() => onStatusChange(key)}
            className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold transition-colors ${
              r.status === key
                ? meta.cls + " ring-1 ring-current"
                : "bg-slate-50 text-slate-400 hover:bg-slate-100"
            }`}>
            {meta.label}
          </button>
        ))}
      </div>
    </div>
  );
}