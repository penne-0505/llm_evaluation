import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, Link } from 'react-router-dom';
import { Settings, Play, BarChart3, LayoutDashboard } from 'lucide-react';
import { useRunStore, MAX_CONCURRENT_JOBS } from '../store/runStore';
import { cancelRun as apiCancelRun } from '../api/client';
import { startBenchmarkSSE } from '../api/sse';
import {
    RunConnectionRegistry,
    type RunCoordinatorActions,
    type StartRunJobRequest,
} from '../api/runCoordinator';

const NAV_ITEMS = [
    { to: '/settings', label: '設定', icon: Settings },
    { to: '/run', label: '実行', icon: Play },
    { to: '/results', label: '結果', icon: BarChart3 },
    { to: '/dashboard', label: 'ダッシュボード', icon: LayoutDashboard },
];

export default function Layout() {
    const location = useLocation();
    const jobs = useRunStore((state) => state.jobs);
    const runningJobs = jobs.filter((j) => j.status === 'running' && j.progress);
    const primary = runningJobs[0] ?? null;
    const progress = primary?.progress ?? null;
    const runId = primary?.runId ?? null;
    const [connectionRegistry] = useState(() => new RunConnectionRegistry());
    const cancelRequestedIdsRef = useRef<Set<string>>(new Set());
    const [liveElapsedMs, setLiveElapsedMs] = useState(progress?.elapsedMs ?? 0);
    const isRunning = runningJobs.length > 0;
    const showRunIndicator = isRunning && location.pathname !== '/run';
    const startedAtMs = progress?.startedAtMs ?? 0;
    const elapsedMs = isRunning ? liveElapsedMs : progress?.elapsedMs ?? 0;
    const totalTaskCount = (progress?.completedTaskCount ?? 0) + (progress?.activeTaskCount ?? 0) + (progress?.queuedTaskCount ?? 0);

    useEffect(() => {
        if (!isRunning || !startedAtMs) {
            return;
        }
        const syncElapsed = () => {
            setLiveElapsedMs(Math.max(0, Date.now() - startedAtMs));
        };
        const frame = window.requestAnimationFrame(syncElapsed);
        const timer = window.setInterval(() => {
            syncElapsed();
        }, 500);
        return () => {
            window.cancelAnimationFrame(frame);
            window.clearInterval(timer);
        };
    }, [isRunning, startedAtMs, primary?.jobId]);

    const startJob = useCallback((request: StartRunJobRequest): string | null => {
        const store = useRunStore.getState();
        if (!store.canStartAnother()) return null;

        const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        store.startJob(jobId, request.label, request.totalSteps);
        connectionRegistry.track(
            jobId,
            startBenchmarkSSE(request.params, jobId),
        );
        return jobId;
    }, [connectionRegistry]);

    const requestCancel = useCallback((jobId: string) => {
        useRunStore.getState().requestJobCancel(jobId);
    }, []);

    const dismissJob = useCallback((jobId: string) => {
        connectionRegistry.abort(jobId);
        cancelRequestedIdsRef.current.delete(jobId);
        useRunStore.getState().dismissJob(jobId);
    }, [connectionRegistry]);

    useEffect(() => {
        for (const job of jobs) {
            if (!job.cancelRequested || !job.runId) continue;
            if (cancelRequestedIdsRef.current.has(job.jobId)) continue;
            cancelRequestedIdsRef.current.add(job.jobId);
            void apiCancelRun(job.runId).catch((error: unknown) => {
                cancelRequestedIdsRef.current.delete(job.jobId);
                useRunStore.getState().failJobCancel(
                    job.jobId,
                    error instanceof Error
                        ? `キャンセル要求に失敗しました: ${error.message}`
                        : 'キャンセル要求に失敗しました',
                );
            });
        }
    }, [jobs]);

    useEffect(() => () => {
        // intent-invariant: INV-004 (Core/concurrent-evaluation-jobs) —
        // nested route changes retain Layout; only app-shell teardown aborts active streams.
        connectionRegistry.abortAll();
        cancelRequestedIdsRef.current.clear();
    }, [connectionRegistry]);

    const runCoordinator = useMemo<RunCoordinatorActions>(() => ({
        startJob,
        requestCancel,
        dismissJob,
    }), [dismissJob, requestCancel, startJob]);

    return (
        <div className="flex h-screen overflow-hidden">
            <div
                className="fixed pointer-events-none z-0"
                style={{
                    top: '-120px',
                    left: '-120px',
                    width: '500px',
                    height: '500px',
                    background: 'radial-gradient(circle, rgba(226, 168, 75, 0.03) 0%, transparent 70%)',
                }}
            />

            <aside
                className="shrink-0 w-[220px] bg-surface border-r border-border flex flex-col z-10 relative"
            >
                <div className="px-4 py-5 overflow-hidden">
                    <div className="whitespace-nowrap overflow-hidden">
                        <h1 className="text-[13px] font-semibold text-text-primary font-display">
                            LLM評価
                        </h1>
                        <p className="text-[9px] text-text-tertiary tracking-wider uppercase">評価スイート</p>
                    </div>
                </div>

                <nav className="flex-1 px-2 space-y-0.5 mt-2">
                    {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                        <NavLink
                            key={to}
                            to={to}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] font-medium transition-all duration-150 group/item ${isActive
                                    ? 'text-amber bg-amber-dim accent-bar-amber'
                                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                                }`
                            }
                        >
                            <Icon size={16} strokeWidth={1.8} className="shrink-0" />
                            <span className="whitespace-nowrap overflow-hidden">
                                {label}
                            </span>
                        </NavLink>
                    ))}
                </nav>

                <div className="px-3 py-3 border-t border-border">
                    <p className="text-[9px] text-text-tertiary whitespace-nowrap">
                        v1.0.0 · 試作版
                    </p>
                </div>
            </aside>

            <main className="flex-1 overflow-y-auto bg-bg relative">
                {showRunIndicator && (
                    <div className="sticky top-0 z-20 flex justify-end px-8 pt-4">
                        <Link
                            to="/run"
                            className="inline-flex items-center gap-3 rounded-md border border-amber/20 bg-surface/95 px-3 py-2 text-[11px] text-text-secondary backdrop-blur hover:border-amber/35 hover:text-text-primary transition-colors"
                        >
                            <span className="inline-flex h-2 w-2 rounded-full bg-amber animate-pulse-amber" />
                            <span className="font-display uppercase tracking-[0.18em] text-[9px] text-amber">
                                実行中 {runningJobs.length}/{MAX_CONCURRENT_JOBS}
                            </span>
                            <span>{progress?.completedTaskCount || 0}/{totalTaskCount || 0} タスク</span>
                            <span>{formatElapsed(elapsedMs)}</span>
                            {runId && (
                                <span className="hidden lg:inline text-text-tertiary">{runId.split('_').slice(0, 2).join('_')}</span>
                            )}
                        </Link>
                    </div>
                )}
                <div className="max-w-[1120px] mx-auto px-8 py-8">
                    <Outlet context={runCoordinator} />
                </div>
            </main>
        </div>
    );
}

function formatElapsed(ms: number): string {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
