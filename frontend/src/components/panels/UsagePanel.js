import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";
import { api } from "../../lib/api";
import { usePoll } from "../../lib/usePoll";

function Stat({ label, value, tone = "text-slate-100", testId }) {
  return (
    <div className="card-surface p-4">
      <p className="eyebrow">{label}</p>
      <p className={`font-head text-2xl font-bold ${tone}`} data-testid={testId}>{value}</p>
    </div>
  );
}

export default function UsagePanel() {
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    api.usage().then((r) => setData(r.data)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);
  usePoll(load, 5000);

  if (!data) return <div className="eyebrow animate-pulse">Loading usage…</div>;

  const chart = data.per_key.map((k) => ({ name: k.mask, requests: k.requests, failures: k.failures }));

  return (
    <div>
      <p className="eyebrow">ANALYTICS</p>
      <h2 className="font-head text-xl font-semibold text-slate-100 mb-5">Usage Dashboard</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label="Total Requests" value={data.total_requests} testId="usage-total" />
        <Stat label="Successful" value={data.successful} tone="text-emerald-400" testId="usage-success" />
        <Stat label="Failed" value={data.failed} tone="text-rose-400" testId="usage-failed" />
        <Stat label="Failovers" value={data.failovers} tone="text-amber-400" testId="usage-failovers" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card-surface p-5 lg:col-span-2">
          <h3 className="font-head font-semibold text-slate-200 mb-4">Requests per Key</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chart}>
              <XAxis dataKey="name" tick={{ fill: "#64748B", fontSize: 11 }} />
              <YAxis tick={{ fill: "#64748B", fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#0F1523", border: "1px solid #1E293B", borderRadius: 8, color: "#F8FAFC" }} />
              <Bar dataKey="requests" radius={[6, 6, 0, 0]}>
                {chart.map((_, i) => <Cell key={i} fill="#3B82F6" />)}
              </Bar>
              <Bar dataKey="failures" radius={[6, 6, 0, 0]}>
                {chart.map((_, i) => <Cell key={i} fill="#EF4444" />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card-surface p-5">
          <h3 className="font-head font-semibold text-slate-200 mb-4">Error Breakdown</h3>
          {Object.keys(data.error_breakdown).length === 0 ? (
            <p className="text-sm text-slate-500">No errors recorded.</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(data.error_breakdown).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between text-sm">
                  <span className="font-mono-x text-slate-300">{type}</span>
                  <span className="font-mono-x text-rose-400">{count}</span>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs text-slate-500 mt-4 leading-relaxed border-t border-slate-800 pt-3">{data.note}</p>
        </div>
      </div>

      <div className="card-surface mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left eyebrow border-b border-slate-800">
              <th className="p-3">Key</th><th className="p-3">Requests</th><th className="p-3">Success</th>
              <th className="p-3">Failures</th><th className="p-3">Failovers</th><th className="p-3">Avg Latency</th>
            </tr>
          </thead>
          <tbody>
            {data.per_key.map((k) => (
              <tr key={k.id} className="border-b border-slate-800/60 font-mono-x text-slate-300">
                <td className="p-3">{k.mask}</td><td className="p-3">{k.requests}</td>
                <td className="p-3 text-emerald-400">{k.success}</td><td className="p-3 text-rose-400">{k.failures}</td>
                <td className="p-3 text-amber-400">{k.failovers}</td><td className="p-3">{k.avg_latency_ms ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
