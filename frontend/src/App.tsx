import { useEffect, useState } from "react";
import ManagerDashboard from "./ManagerDashboard";

const API_URL = import.meta.env.VITE_API_URL;

type Status = "checking" | "ok" | "error";

function App() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => setStatus(data.status === "ok" ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const label = {
    checking: "Checking…",
    ok: "✅ Connected",
    error: "❌ Unreachable",
  }[status];

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>PTO Management System</h1>
      <p>API: {API_URL}</p>
      <p>Backend status: {label}</p>
      <ManagerDashboard />
    </main>
  );
}

export default App;
