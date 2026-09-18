import { useEffect, useRef } from "react";

// Lightweight polling hook: calls fn immediately-safe via caller's own initial load,
// then on an interval. Uses a ref so the latest closure is always called.
export function usePoll(fn, ms = 5000) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    const id = setInterval(() => ref.current && ref.current(), ms);
    return () => clearInterval(id);
  }, [ms]);
}
