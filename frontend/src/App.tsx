
import { useState } from "react";
import LoginPage from "./LoginPage";
import EmployeeDashboard from "./EmployeeDashboard";
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
        <section>
          <h2>Manager Dashboard</h2>
          <p>Manager PTO approval interface will appear here.</p>
        </section>

      ) : (
        <EmployeeDashboard />
      )}

    </main>
  );
}

export default App;
