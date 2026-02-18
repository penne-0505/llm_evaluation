import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import SettingsPage from './pages/SettingsPage';
import RunPage from './pages/RunPage';
import ResultsPage from './pages/ResultsPage';
import ResultDetailPage from './pages/ResultDetailPage';
import DashboardPage from './pages/DashboardPage';
import { useEffect } from 'react';
import { useHistoryStore } from './store/historyStore';
import { useSettingsStore } from './store/settingsStore';

export default function App() {
  const initializeHistory = useHistoryStore((s) => s.initialize);
  const refreshKeyStatus = useSettingsStore((s) => s.refreshKeyStatus);
  const refreshModels = useSettingsStore((s) => s.refreshModels);
  const refreshTasks = useSettingsStore((s) => s.refreshTasks);

  useEffect(() => {
    initializeHistory();
    refreshKeyStatus();
    refreshModels();
    refreshTasks();
  }, [initializeHistory, refreshKeyStatus, refreshModels, refreshTasks]);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/run" element={<RunPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/results/:runId" element={<ResultDetailPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/settings" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
