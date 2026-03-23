import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  LayoutDashboard,
  Receipt,
  FlaskConical,
  Settings,
  LogOut,
  Cpu,
  Terminal,
} from 'lucide-react';

const navItems = [
  { to: '/', label: 'DASHBOARD', icon: LayoutDashboard, node: '01' },
  { to: '/orders', label: 'ORDRES', icon: Receipt, node: '02' },
  { to: '/backtests', label: 'BACKTESTS', icon: FlaskConical, node: '03' },
  { to: '/connectors', label: 'CONFIG', icon: Settings, node: '04' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* ── Sidebar ─────────────────────────────────────── */}
      <aside className="w-[280px] flex flex-col bg-surface shrink-0 border-r border-border">
        {/* Brand header */}
        <div className="px-5 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/25 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-accent" />
            </div>
            <div>
              <span className="text-[11px] font-bold tracking-[0.14em] text-accent uppercase">
                AGENT_TERMINAL
              </span>
              <span className="text-[9px] text-text-dim tracking-widest ml-1.5">v4.2</span>
            </div>
          </div>
        </div>

        {/* Navigation stack */}
        <div className="flex-1 p-4 flex flex-col">
          <div className="section-header">
            <span className="section-title">NAV_STACK</span>
            <Terminal className="section-icon" />
          </div>

          <nav className="flex flex-col gap-1.5">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 group ${
                    isActive
                      ? 'bg-surface-alt border border-accent/20'
                      : 'border border-transparent hover:bg-surface-alt/50'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                      isActive
                        ? 'bg-accent/15 border border-accent/30'
                        : 'bg-surface-raised border border-border'
                    }`}>
                      <item.icon className={`w-3.5 h-3.5 ${isActive ? 'text-accent' : 'text-text-dim'}`} />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[8px] text-text-dim tracking-[0.15em] leading-none">
                        NODE_{item.node}
                      </span>
                      <span className={`text-[11px] font-semibold tracking-[0.1em] ${
                        isActive ? 'text-accent' : 'text-text-muted group-hover:text-text'
                      }`}>
                        {item.label}
                      </span>
                    </div>
                    {isActive && (
                      <div className="ml-auto led led-blue" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Session footer */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2 mb-3">
            <div className="led led-green" />
            <span className="text-[9px] text-text-muted tracking-[0.14em] uppercase">
              SESSION_ACTIVE
            </span>
          </div>
          <div className="text-[9px] text-text-dim tracking-[0.1em] mb-3">
            {user?.email}
          </div>
          <button
            onClick={logout}
            className="btn-ghost w-full flex items-center justify-center gap-2"
          >
            <LogOut className="w-3 h-3" />
            DISCONNECT
          </button>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-11 shrink-0 border-b border-border bg-surface flex items-center justify-between px-5">
          <div className="flex items-center gap-4">
            <span className="text-[11px] font-bold tracking-[0.14em] text-accent uppercase">
              AGENT_TERMINAL_v4.2
            </span>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-2">
              <div className="led led-green" />
              <span className="text-[9px] text-text-muted tracking-[0.1em] uppercase">
                SYSTEM_OK
              </span>
            </div>
            <div className="h-4 w-px bg-border" />
            <span className="text-[9px] text-text-dim tracking-[0.1em] uppercase">
              CPU_LOAD: --
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="badge role">{user?.role}</span>
            <Settings className="w-3.5 h-3.5 text-text-dim cursor-pointer hover:text-text-muted transition-colors" />
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-4">
          {children}
        </main>

        {/* Bottom bar */}
        <footer className="h-7 shrink-0 border-t border-border bg-surface flex items-center justify-between px-5">
          <div className="flex items-center gap-4">
            <span className="text-[8px] text-text-dim tracking-[0.14em] uppercase">
              LOGIC_STREAM
            </span>
            <span className="text-[8px] text-text-dim tracking-[0.1em]">
              BUFFER_SIZE: 0
            </span>
          </div>
          <span className="text-[8px] text-text-dim tracking-[0.14em] uppercase">
            TAURIC_MARKETS // MULTI_AGENT_PLATFORM
          </span>
        </footer>
      </div>
    </div>
  );
}
