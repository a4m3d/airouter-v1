import { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { fmtTime } from "../status";

const FILTERS = ["all", "success", "failed", "running"];

const actionTone = (a) => {
  if (a === "SUCCESS") return "text-emerald-400";
  if (a === "FAILOVER") return "text-amber-400";
  if (a && a.includes("RETRY")) return "text-cyan-400";
  return "text-rose-400";
};

export default function LogsPanel() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState("all");

  const load = useCallback(() => {
    api.logs(filter === "all" ? null : filter).then((r) => setLogs(r.data)).catch(() => {});
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div>
          <p className="eyebrow">STRUCTURED LOGS</p>
          <h2 className="font-head text-xl font-semibold text-slate-100">Logs</h2>
        </div>
        <div className="flex gap-2">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setFilter(f)} data-testid={`log-filter-${f}`}
              className={`text-xs font-mono-x px-3 py-1.5 rounded-lg border transition-colors ${
                filter === f ? "bg-blue-500/15 border-blue-500/40 text-blue-300" : "border-slate-700 text-slate-400 hover:text-slate-200"
              }`}>{f}</button>
          ))}
        </div>
      </div>

      <div className="card-surface overflow-x-auto">
        <table className="w-full text-xs font-mono-x">
          <thead>
            <tr className="text-left eyebrow border-b border-slate-800">
              <th className="p-3">Time</th><th className="p-3">Request</th><th className="p-3">Status</th>
              <th className="p-3">Error Class</th><th className="p-3">Action</th><th className="p-3">Latency</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 && <tr><td colSpan="6" className="p-6 text-center text-slate-500">No logs.</td></tr>}
            {logs.map((l) => (
              <tr key={l.id} className="border-b border-slate-800/60 text-slate-300" data-testid={`log-row-${l.id}`}>
                <td className="p-3 text-slate-500">{fmtTime(l.created_at)}</td>
                <td className="p-3 text-blue-300">{l.id}</td>
                <td className="p-3">{l.status}</td>
                <td className="p-3 text-rose-400">{l.error_type || "—"}</td>
                <td className={`p-3 ${actionTone(l.action)}`}>{l.action || "—"}</td>
                <td className="p-3">{l.latency_ms ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500 mt-3">Logs never contain prompts, responses, or credentials by default.</p>
    </div>
  );
}
