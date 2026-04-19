import React, { useState, useEffect, useRef } from "react";
import { api } from "../api";

// ── Colour palette ────────────────────────────────────────────────────────────
const PLATFORM_COLORS = {
  YouTube:      "#E24B4A",
  Udemy:        "#7C3AED",
  Coursera:     "#2563EB",
  freeCodeCamp: "#16A34A",
  Medium:       "#64748B",
};

// ── Tiny SVG bar chart (weekly minutes) ───────────────────────────────────────
function WeeklyChart({ data }) {
  if (!data || data.length === 0) return null;

  const W = 580, H = 180, PADDING = { top: 16, right: 12, bottom: 40, left: 44 };
  const chartW = W - PADDING.left - PADDING.right;
  const chartH = H - PADDING.top - PADDING.bottom;

  const maxVal = Math.max(...data.map(d => d.minutes), 1);
  const barW = Math.floor(chartW / data.length) - 6;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ overflow: "visible" }}>
      {/* Y-axis labels */}
      {[0, 0.5, 1].map(frac => {
        const y = PADDING.top + chartH * (1 - frac);
        const val = Math.round(maxVal * frac);
        return (
          <g key={frac}>
            <line
              x1={PADDING.left} x2={PADDING.left + chartW}
              y1={y} y2={y}
              stroke="var(--color-border-tertiary)" strokeWidth={0.5} strokeDasharray="4 4"
            />
            <text
              x={PADDING.left - 6} y={y + 4}
              textAnchor="end" fontSize={10}
              fill="var(--color-text-tertiary)"
            >
              {val}m
            </text>
          </g>
        );
      })}

      {/* Bars */}
      {data.map((d, i) => {
        const x = PADDING.left + i * (chartW / data.length) + (chartW / data.length - barW) / 2;
        const barH = d.minutes === 0 ? 2 : Math.max(4, (d.minutes / maxVal) * chartH);
        const y = PADDING.top + chartH - barH;
        const isToday = i === data.length - 1;

        return (
          <g key={d.week}>
            <rect
              x={x} y={y} width={barW} height={barH}
              rx={4}
              fill={isToday ? "#4F46E5" : "#818CF8"}
              opacity={d.minutes === 0 ? 0.25 : 1}
            />
            <text
              x={x + barW / 2}
              y={PADDING.top + chartH + 14}
              textAnchor="middle" fontSize={10}
              fill="var(--color-text-tertiary)"
            >
              {d.label}
            </text>
            {d.minutes > 0 && (
              <text
                x={x + barW / 2}
                y={y - 4}
                textAnchor="middle" fontSize={9}
                fill={isToday ? "#4F46E5" : "var(--color-text-secondary)"}
                fontWeight={isToday ? "500" : "400"}
              >
                {d.minutes}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ── Radar chart (platform scores) ────────────────────────────────────────────
function RadarChart({ data }) {
  if (!data || data.length === 0) return null;

  const cx = 160, cy = 150, R = 110;
  const sides = data.length;

  function polar(i, r) {
    const angle = (Math.PI * 2 * i) / sides - Math.PI / 2;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  }

  // Grid rings
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Polygon points for data
  const dataPoints = data.map((d, i) => polar(i, (d.score / 100) * R));
  const polygonStr = dataPoints.map(p => `${p.x},${p.y}`).join(" ");

  // Axis label positions (slightly outside R)
  const labelR = R + 22;

  return (
    <svg viewBox="0 0 320 300" width="100%">
      {/* Grid rings */}
      {rings.map(frac => {
        const pts = data.map((_, i) => polar(i, R * frac));
        return (
          <polygon
            key={frac}
            points={pts.map(p => `${p.x},${p.y}`).join(" ")}
            fill="none"
            stroke="var(--color-border-tertiary)"
            strokeWidth={0.5}
          />
        );
      })}

      {/* Axis spokes */}
      {data.map((_, i) => {
        const outer = polar(i, R);
        return (
          <line key={i} x1={cx} y1={cy} x2={outer.x} y2={outer.y}
            stroke="var(--color-border-tertiary)" strokeWidth={0.5} />
        );
      })}

      {/* Data polygon */}
      <polygon
        points={polygonStr}
        fill="#4F46E5" fillOpacity={0.18}
        stroke="#4F46E5" strokeWidth={2}
      />

      {/* Data points */}
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={4}
          fill="#4F46E5" stroke="white" strokeWidth={1.5} />
      ))}

      {/* Labels */}
      {data.map((d, i) => {
        const pos = polar(i, labelR);
        const anchor = pos.x < cx - 5 ? "end" : pos.x > cx + 5 ? "start" : "middle";
        const color = PLATFORM_COLORS[d.platform] || "#64748B";
        return (
          <g key={d.platform}>
            <text
              x={pos.x} y={pos.y - 5}
              textAnchor={anchor} fontSize={10} fontWeight="500"
              fill={color}
            >
              {d.platform === "freeCodeCamp" ? "fCC" : d.platform}
            </text>
            <text
              x={pos.x} y={pos.y + 8}
              textAnchor={anchor} fontSize={9}
              fill="var(--color-text-tertiary)"
            >
              {d.score}%
            </text>
          </g>
        );
      })}

      {/* Center dot */}
      <circle cx={cx} cy={cy} r={3} fill="var(--color-border-secondary)" />
    </svg>
  );
}

// ── Forgetting curve scatter plot ─────────────────────────────────────────────
function ForgettingCurve({ data: rawData, avgRetention }) {
  if (!rawData || rawData.length === 0) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", height: 180,
        color: "var(--color-text-tertiary)", fontSize: 13,
      }}>
        <span style={{ fontSize: 32, marginBottom: 8 }}>🃏</span>
        <p style={{ margin: 0 }}>Review flashcards to see your retention curve</p>
      </div>
    );
  }

  const W = 400, H = 180, PAD = { top: 12, right: 16, bottom: 36, left: 44 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  const maxDays = Math.max(...rawData.map(d => d.days_since_review), 14);

  function toX(days) { return PAD.left + (days / maxDays) * chartW; }
  function toY(pct)  { return PAD.top + chartH - (pct / 100) * chartH; }

  // Ebbinghaus reference curve (S=7 as baseline)
  const curvePoints = Array.from({ length: 50 }, (_, i) => {
    const t = (i / 49) * maxDays;
    const r = Math.exp(-t / 7) * 100;
    return `${toX(t)},${toY(r)}`;
  }).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%">
      {/* Y-axis */}
      {[0, 50, 100].map(v => {
        const y = toY(v);
        return (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + chartW} y1={y} y2={y}
              stroke="var(--color-border-tertiary)" strokeWidth={0.5} strokeDasharray="3 3" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={9}
              fill="var(--color-text-tertiary)">{v}%</text>
          </g>
        );
      })}

      {/* X-axis label */}
      <text x={PAD.left + chartW / 2} y={H - 4} textAnchor="middle"
        fontSize={10} fill="var(--color-text-tertiary)">
        Days since review
      </text>

      {/* Reference curve */}
      <polyline
        points={curvePoints}
        fill="none" stroke="#818CF8" strokeWidth={1.5}
        strokeDasharray="6 3" opacity={0.5}
      />

      {/* Data scatter */}
      {rawData.map((d, i) => {
        const x = toX(d.days_since_review);
        const y = toY(d.retention_pct);
        const color = d.retention_pct > 70 ? "#16A34A" : d.retention_pct > 40 ? "#D97706" : "#E24B4A";
        return (
          <circle key={i} cx={x} cy={y} r={4}
            fill={color} fillOpacity={0.8} stroke="white" strokeWidth={1} />
        );
      })}

      {/* Legend */}
      <line x1={PAD.left + 4} x2={PAD.left + 24} y1={PAD.top + 10} y2={PAD.top + 10}
        stroke="#818CF8" strokeWidth={1.5} strokeDasharray="6 3" />
      <text x={PAD.left + 28} y={PAD.top + 14} fontSize={9}
        fill="var(--color-text-tertiary)">Ebbinghaus baseline</text>
    </svg>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, color = "#4F46E5" }) {
  return (
    <div style={{
      background: "var(--color-background-secondary)",
      borderRadius: "var(--border-radius-md)",
      padding: "14px 16px",
    }}>
      <p style={{
        fontSize: 24, fontWeight: 500, color,
        margin: "0 0 2px", lineHeight: 1,
      }}>{value}</p>
      <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: "0 0 1px" }}>{label}</p>
      {sub && <p style={{ fontSize: 11, color: "var(--color-text-tertiary)", margin: 0 }}>{sub}</p>}
    </div>
  );
}

// ── Main Analytics component ───────────────────────────────────────────────────
export default function Analytics() {
  const [weekly, setWeekly]     = useState([]);
  const [radar, setRadar]       = useState([]);
  const [curve, setCurve]       = useState({ data: [], avg_retention: 0 });
  const [resources, setResources] = useState([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    Promise.all([
      api.weeklyAnalytics(),
      api.platformRadar(),
      api.forgettingCurve(),
      api.resources(),
    ]).then(([w, r, c, res]) => {
      setWeekly(w);
      setRadar(r);
      setCurve(c);
      setResources(res);
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Derived stats from real data
  const totalMinutes    = weekly.reduce((s, w) => s + w.minutes, 0);
  const avgPerWeek      = weekly.length > 0 ? Math.round(totalMinutes / weekly.length) : 0;
  const completed       = resources.filter(r => r.status === "completed").length;
  const inProgress      = resources.filter(r => r.status === "in-progress").length;
  const topPlatform     = radar.sort((a, b) => b.score - a.score)[0];
  const activePlatforms = radar.filter(p => p.count > 0).length;

  if (loading) {
    return (
      <div style={{ padding: "2rem", color: "var(--color-text-secondary)", fontSize: 14 }}>
        Loading analytics…
      </div>
    );
  }

  const hasAnyData = resources.length > 0 || totalMinutes > 0;

  return (
    <div style={{ padding: "2rem", maxWidth: 880, margin: "0 auto" }}>

      {!hasAnyData && (
        <div style={{
          background: "var(--color-background-secondary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "2rem", textAlign: "center",
          color: "var(--color-text-secondary)", fontSize: 14, marginBottom: 24,
        }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
          <p style={{ margin: "0 0 4px", fontWeight: 500, color: "var(--color-text-primary)" }}>
            No data yet
          </p>
          <p style={{ margin: 0 }}>
            Add resources and review flashcards to see your analytics here.
          </p>
        </div>
      )}

      {/* Summary stats */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
        gap: 12, marginBottom: 24,
      }}>
        <StatCard label="Total learning time" value={`${totalMinutes}m`}
          sub="last 8 weeks" color="#4F46E5" />
        <StatCard label="Avg per week" value={`${avgPerWeek}m`}
          sub="minutes" color="#7C3AED" />
        <StatCard label="Completed" value={completed}
          sub={`${inProgress} in progress`} color="#16A34A" />
        <StatCard label="Active platforms" value={activePlatforms}
          sub={topPlatform ? `Best: ${topPlatform.platform === "freeCodeCamp" ? "fCC" : topPlatform?.platform}` : "—"}
          color="#D97706" />
      </div>

      {/* Weekly time-series */}
      <div style={{
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "20px 20px 12px", marginBottom: 20,
      }}>
        <p style={{ fontSize: 14, fontWeight: 500, margin: "0 0 16px",
          color: "var(--color-text-primary)" }}>
          Weekly learning time (minutes)
        </p>
        {totalMinutes === 0 ? (
          <div style={{
            height: 180, display: "flex", alignItems: "center",
            justifyContent: "center", color: "var(--color-text-tertiary)", fontSize: 13,
          }}>
            Log activity to see your weekly progress
          </div>
        ) : (
          <WeeklyChart data={weekly} />
        )}
      </div>

      {/* Radar + Forgetting curve side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "20px 16px",
        }}>
          <div style={{ marginBottom: 12 }}>
            <p style={{ fontSize: 14, fontWeight: 500, margin: "0 0 2px",
              color: "var(--color-text-primary)" }}>
              Platform proficiency
            </p>
            <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", margin: 0 }}>
              Scores from progress + completion
            </p>
          </div>
          {activePlatforms === 0 ? (
            <div style={{
              height: 200, display: "flex", alignItems: "center",
              justifyContent: "center", color: "var(--color-text-tertiary)", fontSize: 13,
              flexDirection: "column", gap: 6,
            }}>
              <span style={{ fontSize: 28 }}>📡</span>
              <span>Add resources to see radar</span>
            </div>
          ) : (
            <RadarChart data={radar} />
          )}
        </div>

        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "20px 16px",
        }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <p style={{ fontSize: 14, fontWeight: 500, margin: "0 0 2px",
                  color: "var(--color-text-primary)" }}>
                  Knowledge retention
                </p>
                <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", margin: 0 }}>
                  Per-card Ebbinghaus model
                </p>
              </div>
              {curve.avg_retention > 0 && (
                <span style={{
                  fontSize: 11, fontWeight: 500,
                  padding: "2px 8px", borderRadius: 20,
                  background: curve.avg_retention > 70
                    ? "#EAF3DE" : curve.avg_retention > 40
                    ? "#FAEEDA" : "#FCEBEB",
                  color: curve.avg_retention > 70
                    ? "#3B6D11" : curve.avg_retention > 40
                    ? "#854F0A" : "#A32D2D",
                }}>
                  avg {curve.avg_retention}%
                </span>
              )}
            </div>
          </div>
          <ForgettingCurve data={curve.data} avgRetention={curve.avg_retention} />
        </div>
      </div>

      {/* Platform breakdown table */}
      {activePlatforms > 0 && (
        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "20px", marginTop: 20,
        }}>
          <p style={{ fontSize: 14, fontWeight: 500, margin: "0 0 16px",
            color: "var(--color-text-primary)" }}>
            Platform breakdown
          </p>
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "var(--color-text-tertiary)" }}>
                {["Platform", "Resources", "Avg progress", "Completed", "Score"].map(h => (
                  <th key={h} style={{
                    textAlign: "left", fontWeight: 500,
                    padding: "4px 0 10px", borderBottom: "0.5px solid var(--color-border-tertiary)",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {radar.map(p => (
                <tr key={p.platform}>
                  <td style={{ padding: "10px 0 6px" }}>
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 6,
                      fontSize: 12, fontWeight: 500,
                    }}>
                      <span style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: PLATFORM_COLORS[p.platform] || "#64748B",
                        display: "inline-block", flexShrink: 0,
                      }} />
                      {p.platform}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 6px", color: "var(--color-text-secondary)" }}>
                    {p.count}
                  </td>
                  <td style={{ padding: "10px 0 6px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{
                        width: 60, height: 5, borderRadius: 4,
                        background: "var(--color-background-secondary)", overflow: "hidden",
                      }}>
                        <div style={{
                          width: `${p.avg_progress}%`, height: "100%",
                          background: PLATFORM_COLORS[p.platform] || "#4F46E5",
                          borderRadius: 4,
                        }} />
                      </div>
                      <span style={{ color: "var(--color-text-secondary)", fontSize: 12 }}>
                        {p.avg_progress}%
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: "10px 0 6px", color: "var(--color-text-secondary)" }}>
                    {p.completed}
                  </td>
                  <td style={{ padding: "10px 0 6px" }}>
                    <span style={{
                      fontSize: 11, fontWeight: 500, padding: "2px 8px",
                      borderRadius: 20,
                      background: p.score > 60 ? "#EAF3DE" : p.score > 30 ? "#FAEEDA" : "var(--color-background-secondary)",
                      color: p.score > 60 ? "#3B6D11" : p.score > 30 ? "#854F0A" : "var(--color-text-secondary)",
                    }}>
                      {p.score}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
