
import { useState } from "react";
import LoginPage from "./LoginPage";
import { useState } from "react";
import LoginPage from "./LoginPage";
import EmployeeDashboard from "./EmployeeDashboard";
import ManagerDashboard from "./ManagerDashboard";
import { setAuthToken } from "./apiClient";
import type { User } from "./types";
import "./App.css";
import { setAuthToken } from "./apiClient";
import type { User } from "./types";
import "./App.css";

function App() {
  const [user, setUser] = useState<User | null>(null);

  function handleLogin(authenticatedUser: User) {
    setUser(authenticatedUser);
  }

  function handleLogout() {
    setAuthToken(null);
    setUser(null);
  }

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <main>
      <header>
        <h1>PTO Management System</h1>
        <p>Welcome, {user.name}!</p>
        <button onClick={handleLogout}>Log Out</button>
      </header>

      <hr />

      {user.role === "manager" ? (
        <ManagerDashboard />
      ) : (
        <EmployeeDashboard />
      )}
      )}

    </main>
  );
}

export default App;
