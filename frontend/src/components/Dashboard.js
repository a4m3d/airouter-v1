import { useEffect, useState, useCallback } from "react";
import {
  Key, BarChart3, Cpu, Activity, Terminal, Sliders, ShieldCheck,
  Power, LogOut, Pause, Play, Bot, Command,
} from "lucide-react";
import { toast } from "sonner";
import { api, clearToken } from "../lib/api";
import { Button } from "./ui/button";
import KeysPanel from "./panels/KeysPanel";
import UsagePanel from "./panels/UsagePanel";
import JobsPanel from "./panels/JobsPanel";
import HealthPanel from "./panels/HealthPanel";
import LogsPanel from "./panels/LogsPanel";
import SettingsPanel from "./panels/SettingsPanel";
import ClientKeysPanel from "./panels/ClientKeysPanel";
import CommandsPanel from "./panels/CommandsPanel";

const TABS = [
  { id: "keys", label: "API KEYS", icon: Key },
  { id: "usage", label: "USAGE", icon: BarChart3 },
  { id: "jobs", label: "JOBS", icon: Cpu },
  { id: "health", label: "HEALTH", icon: Activity },
  { id: "logs", label: "LOGS", icon: Terminal },
  { id: "commands", label: "COMMANDS", icon: Command },
  { id: "settings", label: "SETTINGS", icon: Sliders },
  { id: "client_keys", label: "CLIENT KEYS", icon: ShieldCheck },
];

function Metric({ label, value, tone = "text-slate-100", testId }) {
  return (
    <div className="flex flex-col">
      <span className="eyebrow">{label}</span>
      <span className={`font-head text-lg font-bold ${tone}`} data-testid={testId}>{value}</span>
    </div>
  );
}

export default function Dashboard({ onLogout }) {
  const [tab, setTab] = useState("keys");
  const [stats, setStats] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.dashboard();
      setStats(data);
    } catch (e) {
      /* handled by interceptor */
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, [load]);

  const togglePause = async () => {
    try {
      if (stats?.paused) {
        await api.resume();
        toast.success("Router resumed");
      } else {
        await api.pause();
        toast.warning("Router paused — new requests rejected");
      }
      load();
    } catch (e) {
      toast.error("Action failed");
    }
  };

  const logout = () => {
    clearToken();
    onLogout();
  };

  const k = stats?.keys || {};

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="glass sticky top-0 z-50" data-testid="dashboard-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                <Bot className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h1 className="font-head text-base sm:text-lg font-bold tracking-tight text-slate-100">
                  AI ROUTER CONTROL CENTRE
                </h1>
                <div className="flex items-center gap-2" data-testid="system-status-badge">
                  <span className={`dot ${stats?.system_online ? "dot-healthy" : "dot-exhausted"}`} />
                  <span className="eyebrow">{stats?.system_online ? "System Online" : "Paused"}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                data-testid="pause-resume-button"
                onClick={togglePause}
                variant="outline"
                size="sm"
                className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              >
                {stats?.paused ? <Play className="w-4 h-4 mr-1" /> : <Pause className="w-4 h-4 mr-1" />}
                {stats?.paused ? "Resume" : "Pause"}
              </Button>
              <Button
                data-testid="logout-button"
                onClick={logout}
                variant="outline"
                size="sm"
                className="border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Metric strip */}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-4 mt-4 pt-4 border-t border-slate-800">
            <Metric label="🔑 Keys" value={k.total ?? "—"} testId="keys-total-count" />
            <Metric label="Healthy" value={k.healthy ?? "—"} tone="text-emerald-400" testId="healthy-keys-count" />
            <Metric label="Cooldown" value={k.cooldown ?? "—"} tone="text-amber-400" testId="cooldown-keys-count" />
            <Metric label="Exhausted" value={k.exhausted ?? "—"} tone="text-rose-400" testId="exhausted-keys-count" />
            <Metric label="Active Jobs" value={stats?.active_jobs ?? "—"} tone="text-cyan-400" testId="active-jobs-count" />
            <Metric label="Reqs Today" value={stats?.requests_today ?? "—"} testId="requests-today-count" />
          </div>
          <div className="flex gap-4 mt-2 text-xs text-slate-400 font-mono-x">
            <span data-testid="successful-today">✓ {stats?.successful_today ?? 0} ok</span>
            <span className="text-rose-400" data-testid="failed-today">✗ {stats?.failed_today ?? 0} failed</span>
            <span className="text-amber-400" data-testid="failovers-today">🔄 {stats?.failovers_today ?? 0} failovers</span>
          </div>
        </div>
      </header>

      {/* Nav tabs */}
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 pt-5">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                data-testid={`nav-tab-${t.id.replace("_", "-")}`}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-mono-x tracking-wider whitespace-nowrap transition-colors border ${
                  active
                    ? "bg-blue-500/15 border-blue-500/40 text-blue-300"
                    : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                <Icon className="w-4 h-4" />
                {t.label}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Panel */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 fade-in" key={tab}>
        {tab === "keys" && <KeysPanel onChanged={load} />}
        {tab === "usage" && <UsagePanel />}
        {tab === "jobs" && <JobsPanel />}
        {tab === "health" && <HealthPanel />}
        {tab === "logs" && <LogsPanel />}
        {tab === "commands" && <CommandsPanel />}
        {tab === "settings" && <SettingsPanel />}
        {tab === "client_keys" && <ClientKeysPanel />}
      </main>
    </div>
  );
}
