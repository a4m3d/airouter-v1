import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { Send, Link2, Save, Loader2, Bot, UserPlus, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

export default function TelegramCard() {
  const [status, setStatus] = useState(null);
  const [ids, setIds] = useState("");
  const [busy, setBusy] = useState(null);
  const dirty = useRef(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.telegramStatus();
      setStatus(data);
      if (!dirty.current) setIds((data.admin_ids || []).join(", "));
    } catch (e) { /* noop */ }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  const saveIds = async () => {
    setBusy("save");
    try {
      const arr = ids.split(",").map((s) => s.trim()).filter(Boolean);
      await api.saveSettings({ telegram_admin_ids: arr });
      dirty.current = false;
      toast.success("Admin IDs saved");
      load();
    } catch (e) { toast.error("Failed to save"); }
    finally { setBusy(null); }
  };

  const setWebhook = async () => {
    setBusy("webhook");
    try { await api.telegramSetWebhook(); toast.success("Webhook re-registered"); load(); }
    catch (e) { toast.error("Failed"); }
    finally { setBusy(null); }
  };

  const test = async () => {
    setBusy("test");
    try {
      const { data } = await api.telegramTest();
      if (data.ok) toast.success(`Test alert sent to ${data.sent_to.length} admin(s)`);
      else toast.warning(data.detail || "No admin IDs configured");
    } catch (e) { toast.error("Failed to send"); }
    finally { setBusy(null); }
  };

  const authorize = async (id) => {
    setBusy(`auth-${id}`);
    try {
      await api.telegramAuthorize(id);
      toast.success(`Authorized ${id}`);
      load();
    } catch (e) { toast.error("Failed to authorize"); }
    finally { setBusy(null); }
  };

  if (!status) return null;

  const connected = status.token_configured && status.bot;
  const wh = status.webhook;

  return (
    <div className="card-surface p-6 mt-5" data-testid="telegram-settings-card">
      <div className="flex items-center gap-2 mb-4">
        <Bot className="w-5 h-5 text-cyan-400" />
        <h3 className="font-head font-semibold text-slate-100">Telegram Control</h3>
        <span className={`ml-auto text-xs font-mono-x px-2 py-0.5 rounded border ${connected ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" : "text-rose-400 border-rose-500/30 bg-rose-500/10"}`}>
          {connected ? "connected" : "no token"}
        </span>
        <Button data-testid="telegram-refresh-button" onClick={load} size="sm" variant="outline"
          className="ml-2 border-slate-700 bg-slate-900/60 text-slate-200 h-7 px-2">
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
      </div>

      {connected && (
        <div className="text-xs font-mono-x text-slate-400 space-y-1 mb-4">
          <p>bot: <span className="text-cyan-400">@{status.bot.username}</span></p>
          <p>webhook: {wh && wh.url ? <span className="text-emerald-400">active</span> : <span className="text-amber-400">not set</span>}{wh && wh.pending_update_count ? ` · ${wh.pending_update_count} pending` : ""}</p>
        </div>
      )}

      <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3 mb-4 text-xs text-slate-400 leading-relaxed">
        <b className="text-slate-200">How to get your Telegram ID:</b> open Telegram, message
        <span className="text-cyan-400"> @{status.bot ? status.bot.username : "your bot"} </span>
        and send <code className="text-cyan-400">/start</code>. Since you're not yet an admin, it replies with your numeric ID — and you'll also appear below for one-tap authorize.
      </div>

      {status.pending_users && status.pending_users.length > 0 && (
        <div className="mb-4" data-testid="telegram-pending-users">
          <label className="eyebrow block mb-2">Users who messaged the bot — tap to authorize</label>
          <div className="space-y-2">
            {status.pending_users.map((u) => (
              <div key={u.id} className="flex items-center justify-between bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2">
                <div className="text-xs font-mono-x">
                  <span className="text-slate-200">{u.name}</span>
                  {u.username ? <span className="text-slate-500"> @{u.username}</span> : null}
                  <span className="text-cyan-400"> · {u.id}</span>
                </div>
                <Button data-testid={`authorize-user-${u.id}`} onClick={() => authorize(u.id)} disabled={busy === `auth-${u.id}`}
                  size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white">
                  {busy === `auth-${u.id}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <><UserPlus className="w-4 h-4 mr-1" />Authorize</>}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {connected && (!status.pending_users || status.pending_users.length === 0) && status.admin_ids.length === 0 && (
        <div className="mb-4 flex items-center gap-2 text-xs text-amber-400 font-mono-x" data-testid="telegram-waiting-hint">
          <Loader2 className="w-4 h-4 animate-spin" />
          Waiting for you to message @{status.bot ? status.bot.username : "the bot"} with /start…
        </div>
      )}

      <label className="eyebrow block mb-2">Authorized Admin IDs (comma-separated)</label>
      <div className="flex gap-2 mb-3">
        <Input data-testid="telegram-admin-ids-input" placeholder="123456789, 987654321" value={ids}
          onChange={(e) => { dirty.current = true; setIds(e.target.value); }}
          className="bg-slate-950/60 border-slate-700 text-sm font-mono-x" />
        <Button data-testid="save-telegram-ids-button" onClick={saveIds} disabled={busy === "save"}
          className="bg-blue-600 hover:bg-blue-500 text-white">
          {busy === "save" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
        </Button>
      </div>

      <div className="flex gap-2">
        <Button data-testid="telegram-test-button" onClick={test} disabled={busy === "test"}
          variant="outline" size="sm" className="border-slate-700 bg-slate-900/60 text-slate-200">
          <Send className="w-4 h-4 mr-1" /> Send Test Alert
        </Button>
        <Button data-testid="telegram-webhook-button" onClick={setWebhook} disabled={busy === "webhook"}
          variant="outline" size="sm" className="border-slate-700 bg-slate-900/60 text-slate-200">
          <Link2 className="w-4 h-4 mr-1" /> Re-set Webhook
        </Button>
      </div>
    </div>
  );
}
