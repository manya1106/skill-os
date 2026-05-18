import React, { useState, useEffect } from "react";
import {
  Plus, ExternalLink, Trash2, CheckCircle2, PlayCircle, BookOpen,
} from "lucide-react";
import { PlatformBadge, ProgressBar, EmptyState } from "./ui";
import { api } from "../api";

const PLATFORMS = ["YouTube", "Udemy", "Coursera", "freeCodeCamp", "Medium"];

const STATUS_META = {
  "not-started": { label: "Not started", cls: "bg-slate-100 text-slate-500" },
  "in-progress":  { label: "In progress",  cls: "bg-indigo-50 text-indigo-600" },
  "completed":    { label: "Completed",    cls: "bg-green-50 text-green-600"   },
};

const EMPTY_FORM = {
  platform: "YouTube",
  title: "",
  url: "",
  duration: "",
  tags: "",
};

export default function MyLearning() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState(EMPTY_FORM);
  const [saving, setSaving]       = useState(false);
  const [filter, setFilter]       = useState("all");

  useEffect(() => {
    api.resources()
      .then(setResources)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        platform: form.platform,
        title:    form.title,
        url:      form.url || null,
        duration: form.duration || null,
        tags:     form.tags ? form.tags.split(",").map(t => t.trim()).filter(Boolean) : [],
      };
      const created = await api.createResource(payload);
      setResources(prev => [created, ...prev]);
      setForm(EMPTY_FORM);
      setShowForm(false);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(id, status) {
    try {
      const updated = await api.updateResource(id, { status });
      setResources(prev => prev.map(r => r.id === id ? updated : r));
    } catch (err) {
      console.error(err);
    }
  }

  async function updateProgress(id, progress) {
    try {
      const updated = await api.updateResource(id, { progress });
      setResources(prev => prev.map(r => r.id === id ? updated : r));
    } catch (err) {
      console.error(err);
    }
  }

  async function deleteResource(id) {
    try {
      await api.deleteResource(id);
      setResources(prev => prev.filter(r => r.id !== id));
    } catch (err) {
      // fallback: just remove from local state
      setResources(prev => prev.filter(r => r.id !== id));
    }
  }

  const filtered = filter === "all"
    ? resources
    : resources.filter(r => r.status === filter);

  return (
    <div className="p-8 max-w-5xl mx-auto w-full">
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">My Learning</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {resources.length} resource{resources.length !== 1 ? "s" : ""} tracked
          </p>
        </div>
        <button
          onClick={() => setShowForm(f => !f)}
          className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add resource
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form
          onSubmit={handleAdd}
          className="bg-white border border-slate-200 rounded-2xl p-6 mb-6 space-y-4"
        >
          <p className="text-sm font-bold text-slate-900 mb-2">New resource</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Platform</label>
              <select
                value={form.platform}
                onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              >
                {PLATFORMS.map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Duration (optional)</label>
              <input
                type="text"
                placeholder="e.g. 4h 30min"
                value={form.duration}
                onChange={e => setForm(f => ({ ...f, duration: e.target.value }))}
                className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Title *</label>
            <input
              required
              type="text"
              placeholder="Course or resource title"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">URL (optional)</label>
            <input
              type="url"
              placeholder="https://..."
              value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
              className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Tags (comma separated)</label>
            <input
              type="text"
              placeholder="Python, ML, Deep Learning"
              value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
              className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save resource"}
            </button>
            <button
              type="button"
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
              className="px-5 py-2.5 bg-slate-100 text-slate-700 text-sm font-semibold rounded-xl hover:bg-slate-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {[
          { key: "all",         label: "All" },
          { key: "not-started", label: "Not started" },
          { key: "in-progress", label: "In progress" },
          { key: "completed",   label: "Completed" },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-colors ${
              filter === tab.key
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Resource list */}
      {loading && <p className="text-sm text-slate-400">Loading…</p>}

      {!loading && filtered.length === 0 && (
        <EmptyState
          icon="📚"
          title="No resources here yet"
          sub={filter === "all" ? "Add your first resource above." : `Nothing with status "${filter}".`}
        />
      )}

      <div className="space-y-4">
        {filtered.map(r => (
          <ResourceCard
            key={r.id}
            resource={r}
            onStatusChange={status => updateStatus(r.id, status)}
            onProgressChange={progress => updateProgress(r.id, progress)}
            onDelete={() => deleteResource(r.id)}
          />
        ))}
      </div>
    </div>
  );
}

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
            : <BookOpen className="w-5 h-5 text-slate-300" />
          }
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <PlatformBadge platform={r.platform} />
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sm.cls}`}>
              {sm.label}
            </span>
          </div>

          <p className="font-semibold text-slate-900 text-sm truncate mb-1">{r.title}</p>

          {r.duration && (
            <p className="text-xs text-slate-400 mb-2">{r.duration}</p>
          )}

          {(r.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {r.tags.map(t => (
                <span key={t} className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full">{t}</span>
              ))}
            </div>
          )}

          {/* Progress slider */}
          <div className="flex items-center gap-3">
            <ProgressBar value={r.progress ?? 0} />
            <span className="text-xs font-bold text-slate-500 w-8 text-right shrink-0">
              {r.progress ?? 0}%
            </span>
          </div>
          <input
            type="range" min="0" max="100" step="5"
            value={r.progress ?? 0}
            onChange={e => onProgressChange(Number(e.target.value))}
            className="w-full mt-1 accent-indigo-600"
          />
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0 ml-2">
          {r.url && (
            <a href={r.url} target="_blank" rel="noopener noreferrer"
              className="p-1.5 text-slate-400 hover:text-indigo-600 transition-colors"
              title="Open resource">
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button onClick={onDelete}
            className="p-1.5 text-slate-300 hover:text-red-500 transition-colors"
            title="Remove">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Status selector */}
      <div className="flex gap-2 mt-4 pt-3 border-t border-slate-100">
        {Object.entries(STATUS_META).map(([key, meta]) => (
          <button
            key={key}
            onClick={() => onStatusChange(key)}
            className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold transition-colors ${
              r.status === key ? meta.cls + " ring-1 ring-current" : "bg-slate-50 text-slate-400 hover:bg-slate-100"
            }`}
          >
            {meta.label}
          </button>
        ))}
      </div>
    </div>
  );
}