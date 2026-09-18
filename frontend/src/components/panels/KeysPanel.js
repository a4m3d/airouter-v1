import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Plus, TestTube2, Trash2, Loader2, ArrowUpDown, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";
import { StatusDot, fmtTime } from "../status";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "../ui/dialog";

export default function KeysPanel({ onChanged }) {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ secret: "", label: "", priority: "" });
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.keys();
      setKeys(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); onChanged && onChanged(); };

  const addKey = async () => {
    if (!form.secret.trim()) return toast.error("Enter a key value");
    setAdding(true);
    try {
      const body = { secret: form.secret.trim(), label: form.label.trim() || undefined };
      if (form.priority) body.priority = parseInt(form.priority, 10);
      const { data } = await api.addKey(body);
      if (data.validation?.ok) toast.success(`Key added & validated (${data.validation.latency_ms}ms)`);
      else toast.warning(`Key added but validation failed: ${data.validation?.error_type}`);
      setOpen(false);
      setForm({ secret: "", label: "", priority: "" });
      refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add key");
    } finally {
      setAdding(false);
    }
  };

  const test = async (id) => {
    setBusy(`test-${id}`);
    try {
      const { data } = await api.testKey(id);
      if (data.result.ok) toast.success(`Healthy (${data.result.latency_ms}ms)`);
      else toast.error(`Failed: ${data.result.error_type}`);
      refresh();
    } finally { setBusy(null); }
  };

  const toggle = async (id, enabled) => {
    setBusy(`toggle-${id}`);
    try { await api.toggleKey(id, enabled); refresh(); }
    finally { setBusy(null); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this key permanently?")) return;
    setBusy(`del-${id}`);
    try { await api.delKey(id); toast.success("Key deleted"); refresh(); }
    finally { setBusy(null); }
  };

  const changePriority = async (id, current) => {
    const val = window.prompt("Set priority (lower = higher priority)", current);
    if (val === null) return;
    await api.setPriority(id, parseInt(val, 10));
    toast.success("Priority updated");
    refresh();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="eyebrow">PROVIDER KEY POOL</p>
          <h2 className="font-head text-xl font-semibold text-slate-100">API Keys</h2>
        </div>
        <div className="flex gap-2">
          <Button onClick={refresh} variant="outline" size="sm" className="border-slate-700 bg-slate-900/60 text-slate-200" data-testid="refresh-keys-button">
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="bg-blue-600 hover:bg-blue-500 text-white" data-testid="add-key-button">
                <Plus className="w-4 h-4 mr-1" /> Add Key
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-slate-900 border-slate-700 text-slate-100">
              <DialogHeader>
                <DialogTitle className="font-head">Add Universal API Key</DialogTitle>
                <DialogDescription className="text-slate-400">Validated, encrypted (AES-256-GCM) and never shown again in full.</DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <div>
                  <label className="eyebrow block mb-1">Universal API Key</label>
                  <Input data-testid="add-key-secret-input" type="password" placeholder="sk-emergent-..." value={form.secret}
                    onChange={(e) => setForm({ ...form, secret: e.target.value })}
                    className="bg-slate-950/60 border-slate-700 font-mono-x text-sm" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="eyebrow block mb-1">Label</label>
                    <Input data-testid="add-key-label-input" placeholder="Key #2" value={form.label}
                      onChange={(e) => setForm({ ...form, label: e.target.value })}
                      className="bg-slate-950/60 border-slate-700 text-sm" />
                  </div>
                  <div>
                    <label className="eyebrow block mb-1">Priority</label>
                    <Input data-testid="add-key-priority-input" type="number" placeholder="auto" value={form.priority}
                      onChange={(e) => setForm({ ...form, priority: e.target.value })}
                      className="bg-slate-950/60 border-slate-700 text-sm" />
                  </div>
                </div>
                <p className="text-xs text-slate-500">The key is validated, then encrypted (AES-256-GCM) before storage. It is never shown again in full.</p>
              </div>
              <DialogFooter>
                <Button onClick={addKey} disabled={adding} className="bg-blue-600 hover:bg-blue-500 text-white" data-testid="submit-add-key-button">
                  {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : "Validate & Add"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {loading ? (
        <div className="eyebrow animate-pulse">Loading keys…</div>
      ) : keys.length === 0 ? (
        <div className="card-surface p-10 text-center text-slate-400">No keys yet. Add your first Universal Key.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {keys.map((key) => (
            <div key={key.id} className="card-surface p-5" data-testid={`key-card-${key.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-head font-semibold text-slate-100">{key.label}</h3>
                  <StatusDot status={key.health_status} testId={`key-status-dot-${key.id}`} />
                </div>
                <span className="text-xs font-mono-x px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
                  Priority {key.priority}
                </span>
              </div>
              <div className="masked-key inline-block mb-4" data-testid={`key-masked-value-${key.id}`}>{key.mask}</div>

              <div className="grid grid-cols-3 gap-2 text-center mb-4">
                <div><p className="eyebrow">Success</p><p className="font-mono-x text-sm text-emerald-400">{key.success_rate ?? "—"}{key.success_rate != null ? "%" : ""}</p></div>
                <div><p className="eyebrow">Latency</p><p className="font-mono-x text-sm text-slate-200">{key.avg_latency_ms ?? "—"}{key.avg_latency_ms != null ? "ms" : ""}</p></div>
                <div><p className="eyebrow">Failovers</p><p className="font-mono-x text-sm text-amber-400">{key.failover_count}</p></div>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-500 mb-4 font-mono-x">
                <span>req {key.request_count} · fail {key.failure_count}</span>
                <span>{fmtTime(key.last_used_at)}</span>
              </div>

              <div className="flex items-center gap-2 pt-3 border-t border-slate-800">
                <Button data-testid={`test-key-button-${key.id}`} onClick={() => test(key.id)} disabled={busy === `test-${key.id}`}
                  size="sm" variant="outline" className="border-slate-700 bg-slate-900/60 text-slate-200 flex-1">
                  {busy === `test-${key.id}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <><TestTube2 className="w-4 h-4 mr-1" />Test</>}
                </Button>
                <Button data-testid={`priority-key-button-${key.id}`} onClick={() => changePriority(key.id, key.priority)}
                  size="sm" variant="outline" className="border-slate-700 bg-slate-900/60 text-slate-200">
                  <ArrowUpDown className="w-4 h-4" />
                </Button>
                <Button data-testid={`delete-key-button-${key.id}`} onClick={() => remove(key.id)}
                  size="sm" variant="outline" className="border-rose-900/60 bg-rose-950/30 text-rose-300 hover:bg-rose-900/40">
                  <Trash2 className="w-4 h-4" />
                </Button>
                <Switch data-testid={`toggle-key-switch-${key.id}`} checked={key.enabled}
                  onCheckedChange={(v) => toggle(key.id, v)} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
