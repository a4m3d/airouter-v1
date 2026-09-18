import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Activity, Loader2 } from "lucide-react";
import { api } from "../../lib/api";
import { StatusDot, fmtTime } from "../status";
import { Button } from "../ui/button";

export default function HealthPanel() {
  const [keys, setKeys] = useState([]);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    api.health().then((r) => setKeys(r.data.keys)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const runCheck = async () => {
    setRunning(true);
    try {
      const { data } = await api.runHealth();
      setKeys(data.keys);
      toast.success("Health check complete");
    } catch (e) {
      toast.error("Health check failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="eyebrow">MONITORING</p>
          <h2 className="font-head text-xl font-semibold text-slate-100">Health</h2>
        </div>
        <Button data-testid="refresh-health-button" onClick={runCheck} disabled={running}
          size="sm" className="bg-blue-600 hover:bg-blue-500 text-white">
          {running ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Activity className="w-4 h-4 mr-1" />}
          Run Health Check
        </Button>
      </div>

      <div className="card-surface overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left eyebrow border-b border-slate-800">
              <th className="p-3">Key</th><th className="p-3">Status</th><th className="p-3">Latency</th>
              <th className="p-3">Last Error</th><th className="p-3">Last Used</th><th className="p-3">Cooldown</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id} className="border-b border-slate-800/60">
                <td className="p-3 font-mono-x text-slate-300">{k.mask}</td>
                <td className="p-3"><StatusDot status={k.health_status} /></td>
                <td className="p-3 font-mono-x text-slate-300">{k.avg_latency_ms ?? "—"}</td>
                <td className="p-3 font-mono-x text-rose-400">{k.last_error_type || "—"}</td>
                <td className="p-3 font-mono-x text-slate-400 text-xs">{fmtTime(k.last_used_at)}</td>
                <td className="p-3 font-mono-x text-amber-400 text-xs">{k.cooldown_until ? fmtTime(k.cooldown_until) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
