import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, Loader2 } from "lucide-react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import TelegramCard from "./TelegramCard";

const NUM_FIELDS = [
  { key: "retry_count", label: "Max Retries (same key)" },
  { key: "cooldown_seconds", label: "Exhaustion Cooldown (s)" },
  { key: "rate_limit_cooldown_seconds", label: "Rate-limit Cooldown (s)" },
  { key: "request_timeout", label: "Request Timeout (s)" },
  { key: "max_concurrent_jobs", label: "Max Concurrent Jobs" },
  { key: "health_check_interval", label: "Health-check Interval (s, 0=off)" },
];

export default function SettingsPanel() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.settings().then((r) => setS(r.data)).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const body = {
        routing_strategy: s.routing_strategy,
        logging_level: s.logging_level,
        retry_count: parseInt(s.retry_count, 10),
        cooldown_seconds: parseInt(s.cooldown_seconds, 10),
        rate_limit_cooldown_seconds: parseInt(s.rate_limit_cooldown_seconds, 10),
        request_timeout: parseInt(s.request_timeout, 10),
        max_concurrent_jobs: parseInt(s.max_concurrent_jobs, 10),
        health_check_interval: parseInt(s.health_check_interval, 10),
      };
      await api.saveSettings(body);
      toast.success("Settings saved");
    } catch (e) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (!s) return <div className="eyebrow animate-pulse">Loading settings…</div>;

  const selectCls = "w-full bg-slate-950/60 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100";

  return (
    <div className="max-w-2xl">
      <p className="eyebrow">CONFIGURATION</p>
      <h2 className="font-head text-xl font-semibold text-slate-100 mb-5">Settings</h2>

      <div className="card-surface p-6 space-y-5">
        <div>
          <label className="eyebrow block mb-2">Routing Strategy</label>
          <select data-testid="settings-routing-strategy-select" className={selectCls}
            value={s.routing_strategy} onChange={(e) => setS({ ...s, routing_strategy: e.target.value })}>
            <option value="priority">Priority + Automatic Failover (default)</option>
            <option value="round_robin">Round Robin</option>
            <option value="lru">Least Recently Used</option>
          </select>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          {NUM_FIELDS.map((f) => (
            <div key={f.key}>
              <label className="eyebrow block mb-2">{f.label}</label>
              <Input data-testid={`settings-${f.key}-input`} type="number" value={s[f.key]}
                onChange={(e) => setS({ ...s, [f.key]: e.target.value })}
                className="bg-slate-950/60 border-slate-700 text-sm font-mono-x" />
            </div>
          ))}
        </div>

        <div>
          <label className="eyebrow block mb-2">Logging Level</label>
          <select data-testid="settings-logging-level-select" className={selectCls}
            value={s.logging_level} onChange={(e) => setS({ ...s, logging_level: e.target.value })}>
            {["DEBUG", "INFO", "WARN", "ERROR"].map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>

        <Button data-testid="settings-save-button" onClick={save} disabled={saving}
          className="bg-blue-600 hover:bg-blue-500 text-white w-full">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Save Settings</>}
        </Button>
      </div>

      <TelegramCard />
    </div>
  );
}
