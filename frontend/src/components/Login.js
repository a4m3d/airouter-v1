import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, KeyRound, Loader2, ArrowRight } from "lucide-react";
import { api, setToken } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

export default function Login({ onAuthed }) {
  const [token, setTok] = useState("");
  const [loading, setLoading] = useState(false);
  const [demo, setDemo] = useState(false);
  const [showToken, setShowToken] = useState(false);

  useEffect(() => {
    api.authConfig()
      .then((r) => { setDemo(!!r.data.demo_login); if (!r.data.demo_login) setShowToken(true); })
      .catch(() => setShowToken(true));
  }, []);

  const enterDemo = async () => {
    setLoading(true);
    try {
      const { data } = await api.demoLogin();
      setToken(data.token);
      toast.success("Welcome to the Control Centre");
      onAuthed();
    } catch (err) {
      toast.error("Could not open the control centre");
      setShowToken(true);
    } finally {
      setLoading(false);
    }
  };

  const submitToken = async (e) => {
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

        <div className="card-surface p-6 space-y-4" data-testid="login-form">
          {demo && (
            <>
              <Button
                data-testid="demo-login-button"
                onClick={enterDemo}
                disabled={loading}
                className="w-full h-12 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-base"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <>Enter Control Centre <ArrowRight className="w-4 h-4 ml-1" /></>}
              </Button>
              <p className="text-xs text-slate-500 text-center">No password needed — one-click access for this instance.</p>
            </>
          )}

          {demo && !showToken && (
            <button
              data-testid="show-token-login"
              onClick={() => setShowToken(true)}
              className="w-full text-xs text-slate-500 hover:text-slate-300 pt-1"
            >
              Use an admin token instead
            </button>
          )}

          {showToken && (
            <form onSubmit={submitToken} className="space-y-3 pt-2 border-t border-slate-800">
              <label className="eyebrow block">Administrator Token</label>
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
              <Button
                data-testid="login-submit-button"
                type="submit"
                disabled={loading}
                variant="outline"
                className="w-full border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-800"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Sign in with token"}
              </Button>
            </form>
          )}

          <p className="text-xs text-slate-500 leading-relaxed pt-1">
            In production, admins open this from the Telegram bot and are verified via Telegram's
            signed Web App data. Secrets never reach the browser.
          </p>
        </div>
      </div>
    </div>
  );
}
