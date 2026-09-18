import { useEffect, useState } from "react";
import "./App.css";
import { Toaster } from "sonner";
import { api, getToken, setToken } from "./lib/api";
import { initTelegram, tgInitData } from "./lib/tg";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    initTelegram();
    const onExpired = () => setAuthed(false);
    window.addEventListener("router-auth-expired", onExpired);
    const tryTelegram = async () => {
      if (getToken()) {
        setBooting(false);
        return;
      }
      const initData = tgInitData();
      if (initData) {
        try {
          const { data } = await api.login({ init_data: initData });
          setToken(data.token);
          setAuthed(true);
        } catch (e) {
          /* fall through to manual login */
        }
      }
      setBooting(false);
    };
    tryTelegram();
    return () => window.removeEventListener("router-auth-expired", onExpired);
  }, []);

  if (booting) {
    return (
      <div className="App flex items-center justify-center min-h-screen">
        <div className="eyebrow animate-pulse">Initialising control centre…</div>
      </div>
    );
  }

  return (
    <div className="App">
      <Toaster theme="dark" position="top-right" richColors />
      {authed ? <Dashboard onLogout={() => setAuthed(false)} /> : <Login onAuthed={() => setAuthed(true)} />}
    </div>
  );
}
