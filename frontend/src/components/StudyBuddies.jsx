import React, { useState, useEffect } from "react";
import { Users, MessageCircle, BookOpen, BarChart2, Zap } from "lucide-react";
import { Avatar, SectionHeader } from "./ui";
import { api } from "../api";

const INTERACTION_MODES = [
  { icon: <BookOpen className="w-4 h-4" />,     label: "Mutual teaching", desc: "Take turns explaining concepts to each other" },
  { icon: <Users className="w-4 h-4" />,         label: "Collaborative",   desc: "Work through problems together in real time"  },
  { icon: <MessageCircle className="w-4 h-4" />, label: "Discussion",      desc: "Debate ideas, quiz each other, review notes"  },
];

export default function StudyBuddies() {
  const [matches, setMatches]   = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [requested, setRequested] = useState(new Set());
  const [scheduleFor, setScheduleFor] = useState(null);
  const [slots, setSlots] = useState([]);

  useEffect(() => {
    Promise.all([api.buddyMatches(), api.buddySessions()])
      .then(([m, s]) => {
        setMatches(m);
        setSessions(s);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function openSchedule(buddy) {
    setScheduleFor(buddy);
    try {
      const s = await api.buddySlots(buddy.id);
      setSlots(s);
    } catch {
      setSlots([]);
    }
  }

  async function bookSlot(buddyId, slot, mode) {
    try {
      await api.scheduleBuddySession(buddyId, {
        mode: mode || "collaborative",
        scheduled_at: slot.start,
        duration_minutes: slot.duration_minutes,
      });
      const s = await api.buddySessions();
      setSessions(s);
      setScheduleFor(null);
    } catch (err) {
      console.error(err);
    }
  }

  async function sendRequest(id) {
    try {
      await api.sendBuddyRequest(id);
      setRequested(prev => new Set([...prev, id]));
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto w-full">
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-100 rounded-2xl p-6 mb-8 flex flex-col sm:flex-row items-start sm:items-center gap-5">
        <div className="w-14 h-14 rounded-2xl bg-purple-600 flex items-center justify-center shrink-0">
          <Users className="w-7 h-7 text-white" />
        </div>
        <div className="flex-1">
          <p className="font-bold text-slate-900 mb-1">Study buddy matching</p>
          <p className="text-sm text-slate-500">
            Students report better effort levels when learning with a peer.
            Matches are based on shared goals, skill level, and pace.
          </p>
        </div>
        <div className="flex items-center gap-2 bg-purple-600 text-white text-sm font-semibold px-4 py-2 rounded-xl shrink-0">
          <Zap className="w-4 h-4" /> {matches.length} matches found
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-4">
          <SectionHeader title="Top matches for you" />
          {loading && <p className="text-sm text-slate-400">Loading…</p>}
          {!loading && matches.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-8">
              No other users yet. Invite friends to join!
            </p>
          )}
          {matches.map(buddy => (
            <BuddyCard
              key={buddy.id} buddy={buddy}
              requested={requested.has(buddy.id)}
              onRequest={() => sendRequest(buddy.id)}
              onSchedule={() => openSchedule(buddy)}
            />
          ))}

          {sessions.length > 0 && (
            <>
              <SectionHeader title="Upcoming sessions" />
              {sessions.map((s) => (
                <div key={s.id} className="bg-white border border-slate-200 rounded-2xl p-4 text-sm">
                  <p className="font-semibold text-slate-900">{s.buddy?.name}</p>
                  <p className="text-slate-500 capitalize">{s.mode} · {s.duration_minutes} min</p>
                  <p className="text-indigo-600 text-xs mt-1">
                    {s.scheduled_at ? new Date(s.scheduled_at).toLocaleString() : "TBD"}
                  </p>
                </div>
              ))}
            </>
          )}
        </div>

        {scheduleFor && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto">
              <h3 className="font-bold text-slate-900 mb-2">Schedule with {scheduleFor.name}</h3>
              <p className="text-xs text-slate-500 mb-4">Pick a time slot</p>
              <div className="space-y-2">
                {slots.map((slot) => (
                  <button
                    key={slot.start}
                    onClick={() => bookSlot(scheduleFor.id, slot, scheduleFor.their_mode)}
                    className="w-full text-left px-4 py-3 border border-slate-200 rounded-xl hover:border-indigo-400 text-sm"
                  >
                    {slot.label}
                  </button>
                ))}
              </div>
              <button onClick={() => setScheduleFor(null)} className="mt-4 text-sm text-slate-500">
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="space-y-4">
          <SectionHeader title="Interaction modes" />
          {INTERACTION_MODES.map(m => (
            <div key={m.label} className="bg-white border border-slate-200 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-2 text-indigo-600">
                {m.icon}
                <p className="font-semibold text-sm text-slate-900">{m.label}</p>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">{m.desc}</p>
            </div>
          ))}
          <div className="bg-gradient-to-br from-indigo-600 to-purple-700 rounded-2xl p-5 text-white">
            <BarChart2 className="w-6 h-6 mb-3 opacity-80" />
            <p className="text-2xl font-bold mb-1">+30%</p>
            <p className="text-sm opacity-80">
              average improvement in course completion when studying with a peer.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function BuddyCard({ buddy, requested, onRequest, onSchedule }) {
  // Derive initials from name since the API returns basic user data
  const initials = buddy.name
    ? buddy.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()
    : "??";

  const colors = ["purple", "amber", "coral", "teal", "blue"];
  // Pick a stable color based on the id string
  const colorKey = colors[buddy.id.charCodeAt(0) % colors.length];

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center gap-5 hover:shadow-sm transition-shadow">
      <div className="relative shrink-0">
        <Avatar initials={initials} colorKey={colorKey} size="lg" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-slate-900 text-sm mb-0.5">{buddy.name}</p>
        <p className="text-xs text-slate-500">
          Level {buddy.level} · {buddy.their_pace || "moderate"} pace · {buddy.their_mode || "collaborative"}
        </p>
        {buddy.shared_goals?.length > 0 && (
          <p className="text-[10px] text-indigo-600 mt-1">
            Shared: {buddy.shared_goals.join(", ")}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2 shrink-0">
        <button
          onClick={onRequest} disabled={requested}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            requested
              ? "bg-green-50 text-green-700 cursor-default"
              : "bg-slate-900 text-white hover:bg-slate-700"
          }`}
        >
          {requested ? "Requested ✓" : "Connect"}
        </button>
        {requested && (
          <button onClick={onSchedule} className="px-4 py-2 rounded-xl text-xs font-semibold border border-indigo-300 text-indigo-700 hover:bg-indigo-50">
            Schedule
          </button>
        )}
      </div>
    </div>
  );
}