import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import AppErrorBoundary from './components/AppErrorBoundary.tsx'

function reportClientError(payload: {
  source: string;
  message: string;
  stack?: string;
  path?: string;
}) {
  void fetch('/api/client-errors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {
    // 送信失敗は握り潰す
  });
}

window.addEventListener('error', (event) => {
  reportClientError({
    source: 'window.error',
    message: event.message || 'Unknown window error',
    stack: event.error?.stack,
    path: window.location.pathname,
  });
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason;
  reportClientError({
    source: 'window.unhandledrejection',
    message: reason instanceof Error ? reason.message : String(reason),
    stack: reason instanceof Error ? reason.stack : undefined,
    path: window.location.pathname,
  });
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </StrictMode>,
)
