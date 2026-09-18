import { useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, KeyRound, Loader2 } from "lucide-react";
import { api, setToken } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

export default function Login({ onAuthed }) {
  const [token, setTok] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!token.trim()) return;
    setLoading(true);
    try {
      const { data } = await api.login({ admin_token: token.trim() });
      setToken(data.token);
      toast.success("Authenticated as administrator");
      onAuthed();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Invalid admin token");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md fade-in">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-11 h-11 rounded-xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <p className="eyebrow">SECURE ACCESS</p>
            <h1 className="font-head text-2xl font-bold tracking-tight text-slate-100">AI Router Control Centre</h1>
          </div>
        </div>

        <form onSubmit={submit} className="card-surface p-6 space-y-4" data-testid="login-form">
          <div>
            <label className="eyebrow block mb-2">Administrator Token</label>
            <div className="relative">
              <KeyRound className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                data-testid="admin-token-input"
                type="password"
                placeholder="Enter admin dashboard token"
                value={token}
                onChange={(e) => setTok(e.target.value)}
                className="pl-9 bg-slate-950/60 border-slate-700 font-mono-x text-sm"
              />
            </div>
          </div>
          <Button
            data-testid="login-submit-button"
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enter Control Centre"}
          </Button>
          <p className="text-xs text-slate-500 leading-relaxed">
            In production, admins open this from the Telegram bot and are verified via Telegram's
            signed Web App data. Tokens and credentials never reach the browser.
          </p>
        </form>
      </div>
    </div>
  );
}
