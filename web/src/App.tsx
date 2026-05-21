import { Route, Routes } from "react-router-dom";
import { TopBar } from "./components/layout/TopBar";
import SessionDetailPage from "./pages/sessions/[id]";
import SessionListPage from "./pages/sessions/list";

export default function App() {
  return (
    <main className="min-h-screen bg-bg-app text-fg">
      <TopBar />
      <Routes>
        <Route element={<SessionListPage />} path="/" />
        <Route element={<SessionListPage />} path="/sessions" />
        <Route element={<SessionDetailPage />} path="/sessions/:id" />
      </Routes>
    </main>
  );
}
