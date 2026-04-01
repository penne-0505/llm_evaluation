import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, Link } from 'react-router-dom';
import { Settings, Play, BarChart3, LayoutDashboard } from 'lucide-react';
import { useRunStore } from '../store/runStore';

const NAV_ITEMS = [
    { to: '/settings', label: '設定', icon: Settings },
    { to: '/run', label: '実行', icon: Play },
    { to: '/results', label: '結果', icon: BarChart3 },
    { to: '/dashboard', label: 'ダッシュボード', icon: LayoutDashboard },
];

export default function Layout() {
    const location = useLocation();
    const status = useRunStore((state) => state.status);
    const progress = useRunStore((state) => state.progress);
    const runId = useRunStore((state) => state.runId);
    const [, setTick] = useState(0);
    const isRunning = status === 'running' && !!progress;
    const showRunIndicator = isRunning && location.pathname !== '/run';
    const startedAtMs = progress?.startedAtMs ?? 0;
    const elapsedMs = isRunning && startedAtMs ? (Date.now() - startedAtMs) : progress?.elapsedMs ?? 0;
    const totalTaskCount = (progress?.completedTaskCount ?? 0) + (progress?.activeTaskCount ?? 0) + (progress?.queuedTaskCount ?? 0);

    useEffect(() => {
        if (!isRunning) {
            return;
        }
        const timer = window.setInterval(() => {
            setTick((value) => value + 1);
        }, 500);
        return () => window.clearInterval(timer);
    }, [isRunning]);

    return (
        <div className="flex h-screen overflow-hidden">
            {/* Ambient Amber Glow */}
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

            {/* Sidebar */}
            <aside
                className="shrink-0 w-[220px] bg-surface border-r border-border flex flex-col z-10 relative"
            >
                {/* Logo */}
                <div className="px-4 py-5 overflow-hidden">
                    <div className="whitespace-nowrap overflow-hidden">
                        <h1 className="text-[13px] font-semibold text-text-primary font-display">
                            LLM評価
                        </h1>
                        <p className="text-[9px] text-text-tertiary tracking-wider uppercase">評価スイート</p>
                    </div>
                </div>

                {/* Navigation */}
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

                {/* Footer */}
                <div className="px-3 py-3 border-t border-border">
                    <p className="text-[9px] text-text-tertiary whitespace-nowrap">
                        v1.0.0 · 試作版
                    </p>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-bg relative">
                {showRunIndicator && (
                    <div className="sticky top-0 z-20 flex justify-end px-8 pt-4">
                        <Link
                            to="/run"
                            className="inline-flex items-center gap-3 rounded-md border border-amber/20 bg-surface/95 px-3 py-2 text-[11px] text-text-secondary backdrop-blur hover:border-amber/35 hover:text-text-primary transition-colors"
                        >
                            <span className="inline-flex h-2 w-2 rounded-full bg-amber animate-pulse-amber" />
                            <span className="font-display uppercase tracking-[0.18em] text-[9px] text-amber">実行中</span>
                            <span>{progress?.completedTaskCount || 0}/{totalTaskCount || 0} タスク</span>
                            <span>{formatElapsed(elapsedMs)}</span>
                            {runId && (
                                <span className="hidden lg:inline text-text-tertiary">{runId.split('_').slice(0, 2).join('_')}</span>
                            )}
                        </Link>
                    </div>
                )}
                <div className="max-w-[1120px] mx-auto px-8 py-8">
                    <Outlet />
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
