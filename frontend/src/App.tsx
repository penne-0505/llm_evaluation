import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { useSettingsStore } from './store/settingsStore';

const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const RunPage = lazy(() => import('./pages/RunPage'));
const ResultsPage = lazy(() => import('./pages/ResultsPage'));
const ResultDetailPage = lazy(() => import('./pages/ResultDetailPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));

function RouteFallback() {
  return <div className="flex items-center justify-center h-64"><div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" /></div>;
}

export default function App() {
  const refreshKeyStatus = useSettingsStore((s) => s.refreshKeyStatus);
  const refreshModels = useSettingsStore((s) => s.refreshModels);
  const refreshTasks = useSettingsStore((s) => s.refreshTasks);
  const refreshStrictPreset = useSettingsStore((s) => s.refreshStrictPreset);

  useEffect(() => {
    refreshKeyStatus();
    refreshModels();
    refreshTasks();
    refreshStrictPreset();
  }, [refreshKeyStatus, refreshModels, refreshTasks, refreshStrictPreset]);

  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
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
      </Suspense>
    </BrowserRouter>
  );
}
