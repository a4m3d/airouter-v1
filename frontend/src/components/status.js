export function statusMeta(status) {
  switch (status) {
    case "healthy":
      return { dot: "dot-healthy", text: "text-emerald-400", label: "Healthy" };
    case "cooldown":
      return { dot: "dot-cooldown", text: "text-amber-400", label: "Cooldown" };
    case "exhausted":
      return { dot: "dot-exhausted", text: "text-rose-400", label: "Exhausted" };
    case "unhealthy":
      return { dot: "dot-unhealthy", text: "text-rose-400", label: "Unhealthy" };
    default:
      return { dot: "dot-unknown", text: "text-slate-400", label: "Unknown" };
  }
}

export function StatusDot({ status, testId }) {
  const m = statusMeta(status);
  return (
    <span className="inline-flex items-center gap-2" data-testid={testId}>
      <span className={`dot ${m.dot}`} />
      <span className={`text-xs font-mono-x ${m.text}`}>{m.label}</span>
    </span>
  );
}

export function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch (e) {
    return iso;
  }
}
