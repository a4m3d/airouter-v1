import { useState } from "react";
import { toast } from "sonner";
import {
  Copy, Terminal, Activity, KeyRound, Power, Rocket, Send,
} from "lucide-react";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api/v1`;

const GROUPS = [
  {
    title: "Monitoring",
    icon: Activity,
    tone: "text-cyan-400",
    items: [
      { cmd: "/start", desc: "Open the control centre & show help" },
      { cmd: "/status", desc: "System status & today's counters" },
      { cmd: "/usage", desc: "Totals: requests, success, failures, failovers" },
      { cmd: "/jobs", desc: "Recent jobs & their status" },
      { cmd: "/logs", desc: "Recent request logs (no secrets/prompts)" },
      { cmd: "/health", desc: "Run health checks on all keys" },
    ],
  },
  {
    title: "Key Management",
    icon: KeyRound,
    tone: "text-emerald-400",
    items: [
      { cmd: "/keys", desc: "List keys with health & priority" },
      { cmd: "/addkey <key>", desc: "Add & validate a new Universal Key (message auto-deleted)" },
      { cmd: "/enable_key", desc: "Enable a key (managed in the API KEYS tab)" },
      { cmd: "/disable_key", desc: "Disable a key (managed in the API KEYS tab)" },
      { cmd: "/test_key", desc: "Test connectivity (managed in the API KEYS tab)" },
      { cmd: "/remove_key", desc: "Remove a key (managed in the API KEYS tab)" },
    ],
  },
  {
    title: "Control",
    icon: Power,
    tone: "text-amber-400",
    items: [
      { cmd: "/pause", desc: "Pause routing — reject new requests" },
      { cmd: "/resume", desc: "Resume routing" },
      { cmd: "/settings", desc: "Configure routing (managed in the SETTINGS tab)" },
    ],
  },
];

function copy(text, label) {
  navigator.clipboard.writeText(text);
  toast.success(`${label} copied`);
}

export default function CommandsPanel() {
  const [model, setModel] = useState("gpt-5.4");
  const curl = `curl -s ${API_BASE}/chat/completions \\
  -H "Authorization: Bearer sk-router-YOUR_CLIENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"${model}","messages":[{"role":"user","content":"Hello"}]}'`;

  return (
    <div data-testid="commands-panel">
      <p className="eyebrow">REFERENCE</p>
      <h2 className="font-head text-xl font-semibold text-slate-100 mb-5">Command Center</h2>

      {/* Telegram commands */}
      <div className="flex items-center gap-2 mb-3">
        <Terminal className="w-4 h-4 text-slate-400" />
        <h3 className="font-head font-semibold text-slate-200">Telegram Bot Commands</h3>
        <span className="eyebrow ml-1">@theairouterbot</span>
      </div>
      <div className="grid gap-4 md:grid-cols-3 mb-8">
        {GROUPS.map((g) => {
          const Icon = g.icon;
          return (
            <div key={g.title} className="card-surface p-5" data-testid={`command-group-${g.title.toLowerCase().replace(/\s/g, "-")}`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`w-4 h-4 ${g.tone}`} />
                <p className="eyebrow">{g.title}</p>
              </div>
              <div className="space-y-3">
                {g.items.map((it) => (
                  <button
                    key={it.cmd}
                    onClick={() => copy(it.cmd.split(" ")[0], it.cmd.split(" ")[0])}
                    className="w-full text-left group"
                    data-testid={`command-${it.cmd.split(" ")[0].replace("/", "")}`}
                  >
                    <div className="flex items-center gap-2">
                      <code className="font-mono-x text-sm text-blue-300 group-hover:text-blue-200">{it.cmd}</code>
                      <Copy className="w-3 h-3 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <p className="text-xs text-slate-500 leading-snug">{it.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Router API quickstart */}
      <div className="flex items-center gap-2 mb-3">
        <Rocket className="w-4 h-4 text-slate-400" />
        <h3 className="font-head font-semibold text-slate-200">Connect a Coding Agent (Cline / OpenAI-compatible)</h3>
      </div>
      <div className="card-surface p-5">
        <div className="grid sm:grid-cols-2 gap-4 mb-5">
          <div>
            <p className="eyebrow mb-2">Base URL</p>
            <div className="flex items-center gap-2">
              <code className="masked-key flex-1 break-all" data-testid="api-base-url">{API_BASE}</code>
              <button onClick={() => copy(API_BASE, "Base URL")} className="text-slate-400 hover:text-slate-200" data-testid="copy-base-url">
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div>
            <p className="eyebrow mb-2">API Key</p>
            <p className="text-sm text-slate-400">Create one under <span className="text-cyan-400 font-mono-x">CLIENT KEYS</span> → it looks like <span className="text-emerald-400 font-mono-x">sk-router-…</span></p>
          </div>
        </div>

        <div className="flex items-center gap-2 mb-2">
          <p className="eyebrow">Example request</p>
          <div className="flex gap-1 ml-auto">
            {["gpt-5.4", "claude-sonnet-4-6", "gemini-3.1-pro-preview"].map((m) => (
              <button key={m} onClick={() => setModel(m)} data-testid={`model-preset-${m}`}
                className={`text-xs font-mono-x px-2 py-1 rounded border transition-colors ${model === m ? "bg-blue-500/15 border-blue-500/40 text-blue-300" : "border-slate-700 text-slate-400 hover:text-slate-200"}`}>
                {m}
              </button>
            ))}
          </div>
        </div>
        <div className="relative">
          <pre className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 text-xs font-mono-x text-slate-300 overflow-x-auto" data-testid="curl-example">{curl}</pre>
          <button onClick={() => copy(curl, "cURL example")} className="absolute top-3 right-3 text-slate-400 hover:text-slate-200" data-testid="copy-curl">
            <Copy className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500 font-mono-x">
          <span><Send className="w-3 h-3 inline mr-1" />Header <span className="text-cyan-400">X-Session-Id</span>: keep a job continuous across failovers</span>
          <span><Send className="w-3 h-3 inline mr-1" />Header <span className="text-cyan-400">Idempotency-Key</span>: safe replay of a completed request</span>
        </div>
      </div>
    </div>
  );
}
