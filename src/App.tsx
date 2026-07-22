import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import type { User } from "./types";
import * as api from "./api";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import LeadsPage from "./pages/LeadsPage";
import PipelinePage from "./pages/PipelinePage";
import LeadCreatePage from "./pages/LeadCreatePage";
import LeadDetailPage from "./pages/LeadDetailPage";
import ImportPage from "./pages/ImportPage";
import ExportPage from "./pages/ExportPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("crm_token");
    if (token) {
      api.getMe()
        .then((u) => setUser({ id: u.id, email: u.email, full_name: u.full_name }))
        .catch(() => localStorage.removeItem("crm_token"))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = (token: string, u: User) => {
    localStorage.setItem("crm_token", token);
    setUser(u);
  };

  const handleLogout = () => {
    localStorage.removeItem("crm_token");
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
        <Route path="/register" element={<RegisterPage onRegister={handleLogin} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Layout user={user} onLogout={handleLogout}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/leads/new" element={<LeadCreatePage />} />
        <Route path="/leads/:id" element={<LeadDetailPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}

export default App;
