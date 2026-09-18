import { useEffect, useState, useCallback } from "react";
import { ArrowRight, CheckCircle2, XCircle, RotateCw } from "lucide-react";
import { api } from "../../lib/api";
import { usePoll } from "../../lib/usePoll";
import { fmtTime } from "../status";

function StatusBadge({ status }) {
  const map = {
    success: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    running: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
    failed: "text-rose-400 border-rose-500/30 bg-rose-500/10",
  };
  return <span className={`text-xs font-mono-x px-2 py-0.5 rounded border ${map[status] || "text-slate-400 border-slate-700 bg-slate-800"}`}>{status}</span>;
}

export default function JobsPanel() {
  const [jobs, setJobs] = useState([]);
  const [detail, setDetail] = useState(null);

  const load = useCallback(() => {
    api.jobs().then((r) => setJobs(r.data)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);
  usePoll(load, 5000);

  const openJob = async (id) => {
    const { data } = await api.jobDetail(id);
    setDetail(data);
  };

  return (
    <div>
      <p className="eyebrow">SESSION CONTINUITY</p>
      <h2 className="font-head text-xl font-semibold text-slate-100 mb-5">Jobs</h2>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card-surface overflow-hidden">
          <div className="max-h-[520px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900/90 backdrop-blur">
                <tr className="text-left eyebrow border-b border-slate-800">
                  <th className="p-3">Job</th><th className="p-3">Model</th><th className="p-3">Step</th><th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 && <tr><td colSpan="4" className="p-6 text-center text-slate-500">No jobs yet.</td></tr>}
                {jobs.map((j) => (
                  <tr key={j.id} onClick={() => openJob(j.id)}
                    className="border-b border-slate-800/60 cursor-pointer hover:bg-slate-800/40" data-testid={`job-row-${j.id}`}>
                    <td className="p-3 font-mono-x text-blue-300">{j.id}</td>
                    <td className="p-3 font-mono-x text-slate-300">{j.model}</td>
                    <td className="p-3 font-mono-x text-slate-400">{j.current_step}</td>
                    <td className="p-3"><StatusBadge status={j.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card-surface p-5" data-testid={detail ? `job-timeline-${detail.job.id}` : "job-timeline-empty"}>
          {!detail ? (
            <p className="text-slate-500 text-sm">Select a job to view its failover timeline.</p>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-head font-semibold text-slate-100">{detail.job.id}</h3>
                <StatusBadge status={detail.job.status} />
              </div>
              <div className="text-xs font-mono-x text-slate-400 space-y-1 mb-5">
                <p>session: {detail.job.session_id}</p>
                <p>model: {detail.job.provider} / {detail.job.model}</p>
                <p>retries: {detail.job.retry_count}</p>
              </div>
              <p className="eyebrow mb-3">EXECUTION TIMELINE</p>
              <div className="space-y-3">
                {detail.requests.map((r) => (
                  <div key={r.id} className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {r.status === "success" ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        : r.status === "failed" ? <XCircle className="w-4 h-4 text-rose-400" />
                        : <RotateCw className="w-4 h-4 text-amber-400" />}
                    </div>
                    <div className="flex-1 text-xs font-mono-x">
                      <p className="text-slate-200">Step {r.step || "?"} · {r.action || r.status}</p>
                      <p className="text-slate-500">{r.error_type ? `${r.error_type} · ` : ""}{r.latency_ms ? `${r.latency_ms}ms · ` : ""}{fmtTime(r.created_at)}</p>
                    </div>
                  </div>
                ))}
                {detail.failovers.map((f) => (
                  <div key={f.id} className="flex items-center gap-2 text-xs font-mono-x text-amber-400 pl-7">
                    key <ArrowRight className="w-3 h-3" /> key · {f.reason}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
