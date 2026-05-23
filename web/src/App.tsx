import { Route, Routes } from "react-router-dom";
import { RequireAuth } from "./components/RequireAuth";
import { TopBar } from "./components/layout/TopBar";
import LoginPage from "./pages/LoginPage";
import SessionDetailPage from "./pages/sessions/[id]";
import SessionListPage from "./pages/sessions/list";

export default function App() {
  return (
    <main className="min-h-screen bg-bg-app text-fg">
      <TopBar />
      <Routes>
        <Route element={<LoginPage />} path="/login" />
        <Route element={<RequireAuth><SessionListPage /></RequireAuth>} path="/" />
        <Route element={<RequireAuth><SessionListPage /></RequireAuth>} path="/sessions" />
        <Route element={<RequireAuth><SessionDetailPage /></RequireAuth>} path="/sessions/:id" />
      </Routes>
    </main>
  );
}
