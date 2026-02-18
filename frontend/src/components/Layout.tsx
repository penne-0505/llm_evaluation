import { NavLink, Outlet } from 'react-router-dom';
import { Settings, Play, BarChart3, LayoutDashboard, Pin, PinOff } from 'lucide-react';
import { useState } from 'react';

const NAV_ITEMS = [
    { to: '/settings', label: 'Settings', icon: Settings },
    { to: '/run', label: 'Run', icon: Play },
    { to: '/results', label: 'Results', icon: BarChart3 },
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
];

export default function Layout() {
    const [pinned, setPinned] = useState(false);

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
                className={`group shrink-0 bg-surface border-r border-border flex flex-col transition-all duration-200 ease-out z-10 relative ${pinned ? 'w-[220px]' : 'w-[56px] hover:w-[220px]'
                    }`}
            >
                {/* Logo */}
                <div className="px-4 py-5 flex items-center gap-3 overflow-hidden">
                    <div className="w-7 h-7 shrink-0 rounded-md bg-amber/10 border border-amber/20 flex items-center justify-center">
                        <span className="text-amber font-display font-bold text-[11px]">LB</span>
                    </div>
                    <div className={`whitespace-nowrap overflow-hidden transition-opacity duration-200 ${pinned ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                        <h1 className="text-[13px] font-semibold text-text-primary font-display">
                            LLM Bench
                        </h1>
                        <p className="text-[9px] text-text-tertiary tracking-wider uppercase">Evaluation Suite</p>
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
                            <span className={`whitespace-nowrap overflow-hidden transition-opacity duration-200 ${pinned ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                {label}
                            </span>
                        </NavLink>
                    ))}
                </nav>

                {/* Footer */}
                <div className="px-3 py-3 border-t border-border flex items-center justify-between">
                    <p className={`text-[9px] text-text-tertiary whitespace-nowrap transition-opacity duration-200 ${pinned ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                        v1.0.0 · Prototype
                    </p>
                    <button
                        onClick={() => setPinned(!pinned)}
                        className={`text-text-tertiary hover:text-amber transition-colors shrink-0 ${pinned ? '' : 'opacity-0 group-hover:opacity-100'}`}
                        title={pinned ? 'Unpin sidebar' : 'Pin sidebar'}
                    >
                        {pinned ? <PinOff size={12} /> : <Pin size={12} />}
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-bg relative">
                <div className="max-w-[1120px] mx-auto px-8 py-8">
                    <Outlet />
                </div>
            </main>
        </div>
    );
}
