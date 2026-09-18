import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const getToken = () => localStorage.getItem("router_admin_token");
export const setToken = (t) => localStorage.setItem("router_admin_token", t);
export const clearToken = () => localStorage.removeItem("router_admin_token");

const client = axios.create({ baseURL: API });
client.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});
client.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response && e.response.status === 401) {
      clearToken();
      window.location.reload();
    }
    return Promise.reject(e);
  }
);

export const api = {
  login: (payload) => axios.post(`${API}/auth/login`, payload),
  dashboard: () => client.get("/admin/dashboard"),
  keys: () => client.get("/admin/keys"),
  addKey: (b) => client.post("/admin/keys", b),
  delKey: (id) => client.delete(`/admin/keys/${id}`),
  toggleKey: (id, enabled) => client.post(`/admin/keys/${id}/enabled`, { enabled }),
  setPriority: (id, priority) => client.post(`/admin/keys/${id}/priority`, { priority }),
  testKey: (id) => client.post(`/admin/keys/${id}/test`),
  usage: () => client.get("/admin/usage"),
  jobs: () => client.get("/admin/jobs"),
  jobDetail: (id) => client.get(`/admin/jobs/${id}`),
  health: () => client.get("/admin/health"),
  runHealth: () => client.post("/admin/health/check"),
  logs: (status) => client.get("/admin/logs", { params: status ? { status } : {} }),
  settings: () => client.get("/admin/settings"),
  saveSettings: (b) => client.put("/admin/settings", b),
  pause: () => client.post("/admin/pause"),
  resume: () => client.post("/admin/resume"),
  clientKeys: () => client.get("/admin/client-keys"),
  createClientKey: (b) => client.post("/admin/client-keys", b),
  revokeClientKey: (id) => client.post(`/admin/client-keys/${id}/revoke`),
  rotateClientKey: (id) => client.post(`/admin/client-keys/${id}/rotate`),
  telegramStatus: () => client.get("/admin/telegram"),
  telegramSetWebhook: () => client.post("/admin/telegram/set-webhook"),
  telegramTest: () => client.post("/admin/telegram/test"),
};
