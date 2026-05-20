
// frontend/src/components/TestingDashboard.jsx
import React, { useState, useEffect } from "react";
import { Activity, Users, Zap, TrendingUp } from "lucide-react";

export default function TestingDashboard() {
  const [metrics, setMetrics] = useState({
    totalUsers: 0,
    totalEvents: 0,
    averageXP: 0,
    averageStreak: 0,
    dashboardsActive: 0,
    lastUpdate: new Date(),
  });

  useEffect(() => {
    // Poll for metrics every 5 seconds
    const interval = setInterval(async () => {
      try {
        const res = await fetch("http://localhost:8000/admin/test-metrics");
        if (res.ok) {
          setMetrics(await res.json());
        }
      } catch (e) {
        console.error("Metrics fetch failed:", e);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const StatCard = ({ icon: Icon, label, value, unit }) => (
    <div className="bg-white rounded-lg p-5 shadow-sm border border-slate-200">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-slate-600">{label}</p>
        <Icon className="w-5 h-5 text-indigo-500" />
      </div>
      <p className="text-2xl font-bold">
        {value.toLocaleString()} <span className="text-sm text-slate-400">{unit}</span>
      </p>
    </div>
  );

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">🧪 Test Metrics</h1>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard icon={Users} label="Total Users" value={metrics.totalUsers} unit="users" />
        <StatCard icon={Activity} label="Events Generated" value={metrics.totalEvents} unit="events" />
        <StatCard icon={Zap} label="Avg XP" value={metrics.averageXP} unit="XP" />
        <StatCard icon={TrendingUp} label="Avg Streak" value={metrics.averageStreak} unit="days" />
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
        Last updated: {metrics.lastUpdate.toLocaleTimeString()}
      </div>
    </div>
  );
}