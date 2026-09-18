import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Plus, RotateCw, Ban, Copy, Loader2, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import { usePoll } from "../../lib/usePoll";
import { fmtTime } from "../status";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "../ui/dialog";

export default function ClientKeysPanel() {
  const [keys, setKeys] = useState([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [reveal, setReveal] = useState(null);
  const [showRevoked, setShowRevoked] = useState(false);

  const load = useCallback(() => {
    api.clientKeys().then((r) => setKeys(r.data)).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);
  usePoll(load, 6000);

  const create = async () => {
    setCreating(true);
    try {
      const { data } = await api.createClientKey({ name: name.trim() || "client" });
      setReveal(data.plaintext);
      setOpen(false);
      setName("");
      load();
    } catch (e) {
      toast.error("Failed to create client key");
    } finally {
      setCreating(false);
    }
  };

  const rotate = async (id) => {
    const { data } = await api.rotateClientKey(id);
    setReveal(data.plaintext);
    load();
  };

  const revoke = async (id) => {
    if (!window.confirm("Revoke this client key?")) return;
    await api.revokeClientKey(id);
    toast.success("Client key revoked");
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Permanently delete this client key?")) return;
    await api.deleteClientKey(id);
    toast.success("Client key deleted");
    load();
  };

  const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied to clipboard"); };

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="eyebrow">ROUTER ACCESS</p>
          <h2 className="font-head text-xl font-semibold text-slate-100">Client Keys</h2>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-500 text-white" data-testid="create-client-key-button">
              <Plus className="w-4 h-4 mr-1" /> Create Client Key
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-slate-900 border-slate-700 text-slate-100">
            <DialogHeader>
              <DialogTitle className="font-head">New Router Client Key</DialogTitle>
              <DialogDescription className="text-slate-400">Issued to a coding agent; the full key is shown only once.</DialogDescription>
            </DialogHeader>
            <div>
              <label className="eyebrow block mb-1">Name</label>
              <Input data-testid="client-key-name-input" placeholder="Cline on my laptop" value={name}
                onChange={(e) => setName(e.target.value)} className="bg-slate-950/60 border-slate-700 text-sm" />
              <p className="text-xs text-slate-500 mt-2">Agents authenticate with this key via <code className="text-cyan-400">Authorization: Bearer sk-router-…</code></p>
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={creating} className="bg-blue-600 hover:bg-blue-500 text-white" data-testid="submit-client-key-button">
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {reveal && (
        <div className="card-surface p-4 mb-5 border-emerald-500/30" data-testid="client-key-reveal">
          <p className="eyebrow text-emerald-400 mb-2">COPY NOW — SHOWN ONCE</p>
          <div className="flex items-center gap-2">
            <code className="masked-key flex-1 break-all">{reveal}</code>
            <Button size="sm" onClick={() => copy(reveal)} className="bg-emerald-600 hover:bg-emerald-500 text-white">
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      <div className="card-surface overflow-x-auto">
        <div className="flex items-center justify-end px-3 pt-3">
          <label className="flex items-center gap-2 text-xs text-slate-400 font-mono-x cursor-pointer" data-testid="show-revoked-toggle">
            <input type="checkbox" checked={showRevoked} onChange={(e) => setShowRevoked(e.target.checked)} />
            Show revoked
          </label>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left eyebrow border-b border-slate-800">
              <th className="p-3">Name</th><th className="p-3">Prefix</th><th className="p-3">Requests</th>
              <th className="p-3">Status</th><th className="p-3">Created</th><th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(() => {
              const rows = keys.filter((k) => showRevoked || k.enabled);
              if (rows.length === 0) return <tr><td colSpan="6" className="p-6 text-center text-slate-500">No active client keys.</td></tr>;
              return rows.map((k) => (
              <tr key={k.id} className="border-b border-slate-800/60" data-testid={`client-key-row-${k.id}`}>
                <td className="p-3 text-slate-200">{k.name}</td>
                <td className="p-3 font-mono-x text-cyan-400">{k.key_prefix}…</td>
                <td className="p-3 font-mono-x text-slate-300">{k.request_count}</td>
                <td className="p-3">
                  <span className={`text-xs font-mono-x px-2 py-0.5 rounded border ${k.enabled ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" : "text-rose-400 border-rose-500/30 bg-rose-500/10"}`}>
                    {k.enabled ? "active" : "revoked"}
                  </span>
                </td>
                <td className="p-3 text-xs text-slate-500 font-mono-x">{fmtTime(k.created_at)}</td>
                <td className="p-3 flex gap-2">
                  {k.enabled && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => rotate(k.id)} data-testid={`rotate-client-key-${k.id}`}
                        className="border-slate-700 bg-slate-900/60 text-slate-200"><RotateCw className="w-4 h-4" /></Button>
                      <Button size="sm" variant="outline" onClick={() => revoke(k.id)} data-testid={`revoke-client-key-${k.id}`}
                        className="border-amber-900/60 bg-amber-950/30 text-amber-300"><Ban className="w-4 h-4" /></Button>
                    </>
                  )}
                  <Button size="sm" variant="outline" onClick={() => remove(k.id)} data-testid={`delete-client-key-${k.id}`}
                    className="border-rose-900/60 bg-rose-950/30 text-rose-300"><Trash2 className="w-4 h-4" /></Button>
                </td>
              </tr>
              ));
            })()}
          </tbody>
        </table>
      </div>
    </div>
  );
}
