import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Building2, LogOut, Menu, X, ChevronDown, Bell, MoreHorizontal } from 'lucide-react';
import useAuthStore from '../../store/authStore';
import { authAPI } from '../../lib/api';
import { toast } from 'sonner';

/**
 * Unified Role Layout
 * - Desktop (>=1024px): Dark sidebar (240px) + 56px white top bar
 * - Mobile (<1024px): 52px top bar + bottom nav (5 items) + drawer for "More"
 * - Applies role accent class (.role-platform/.role-admin/.role-sub_admin/.role-resident)
 *
 * Props:
 *   role: 'platform_owner' | 'admin' | 'sub_admin' | 'resident'
 *   roleLabel: short label for top bar (e.g., "Admin")
 *   navItems: [{ path, icon, label, mobile? }] — `mobile: true` includes in mobile bottom nav (max 4 + More)
 *   children
 */
const RoleLayout = ({ role, roleLabel, navItems, children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, switchRole } = useAuthStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [roles, setRoles] = useState([]);
  const [showRoleSwitch, setShowRoleSwitch] = useState(false);

  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const res = await authAPI.getRoles();
        setRoles(res.data);
      } catch (e) {
        // optional feature
      }
    };
    fetchRoles();
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
    toast.success('Logged out');
  };

  const handleRoleSwitch = async (r) => {
    try {
      const res = await authAPI.switchRole(r);
      switchRole(res.data.user, res.data.access_token);
      toast.success(`Switched to ${r.replace('_', ' ')}`);
      switch (r) {
        case 'platform_owner': navigate('/platform'); break;
        case 'admin': navigate('/admin'); break;
        case 'sub_admin': navigate('/subadmin'); break;
        case 'resident': navigate('/resident'); break;
        default: navigate('/');
      }
    } catch (e) {
      toast.error('Failed to switch role');
    }
    setShowRoleSwitch(false);
  };

  const isActive = (path) => location.pathname === path;
  const roleClass = `role-${role}`;

  // Mobile bottom nav: first 4 navItems with mobile:true (or first 4 overall) + More button
  const mobileItems = navItems.filter((i) => i.mobile !== false).slice(0, 4);
  const moreItems = navItems.filter((i) => !mobileItems.includes(i));

  const initial = user?.name?.charAt(0)?.toUpperCase() || 'U';

  return (
    <div className={`${roleClass} min-h-screen`} style={{ backgroundColor: '#F8F8F6' }} data-testid={`layout-${role}`}>
      {/* ============ DESKTOP SIDEBAR ============ */}
      <aside
        className="hidden lg:flex fixed top-0 left-0 z-40 h-screen w-60 flex-col"
        style={{ backgroundColor: '#0F172A' }}
        data-testid="desktop-sidebar"
      >
        {/* Brand */}
        <div className="px-5 py-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
          <div className="flex items-center gap-2.5">
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: 'var(--accent-raw)' }}
            >
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-white font-medium text-[14px] leading-tight">SocietyHub</div>
              <div className="text-[10px] uppercase tracking-wider mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                {roleLabel}
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto scrollbar-thin space-y-0.5">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
              className={`sidebar-item ${isActive(item.path) ? 'sidebar-item-active' : ''}`}
            >
              <item.icon className="w-[18px] h-[18px]" />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        {/* User block */}
        <div className="px-3 py-3 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
          {roles.length > 1 && (
            <div className="mb-2 relative">
              <button
                onClick={() => setShowRoleSwitch(!showRoleSwitch)}
                data-testid="role-switch-btn"
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-[12px]"
                style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.8)' }}
              >
                <span>Switch Role</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showRoleSwitch ? 'rotate-180' : ''}`} />
              </button>
              {showRoleSwitch && (
                <div
                  className="absolute bottom-full left-0 right-0 mb-1 rounded-lg overflow-hidden"
                  style={{ backgroundColor: '#1E293B', border: '1px solid rgba(255,255,255,0.08)' }}
                >
                  {roles.map((r) => (
                    <button
                      key={r.role}
                      onClick={() => handleRoleSwitch(r.role)}
                      data-testid={`switch-to-${r.role}`}
                      className="w-full px-3 py-2 text-left text-[12px] hover:bg-white/5"
                      style={{ color: 'rgba(255,255,255,0.85)' }}
                    >
                      {r.role.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <div className="avatar-circle" style={{ width: 32, height: 32 }}>{initial}</div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-[12px] font-medium truncate">{user?.name}</p>
              <p className="text-[10px] truncate" style={{ color: 'rgba(255,255,255,0.5)' }}>{user?.mobile}</p>
            </div>
            <button
              onClick={handleLogout}
              data-testid="logout-btn"
              className="p-1.5 rounded hover:bg-white/10"
              title="Logout"
            >
              <LogOut className="w-4 h-4" style={{ color: 'rgba(255,255,255,0.7)' }} />
            </button>
          </div>
        </div>
      </aside>

      {/* ============ TOP BAR ============ */}
      <header className="topbar fixed top-0 left-0 right-0 lg:left-60 z-30" data-testid="topbar">
        <button
          onClick={() => setDrawerOpen(true)}
          className="lg:hidden p-1.5 -ml-1.5 rounded hover:bg-black/5"
          data-testid="mobile-menu-btn"
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" style={{ color: '#1A1A18' }} />
        </button>

        <div className="flex-1 min-w-0">
          <h2 className="text-[14px] font-medium truncate" style={{ color: '#1A1A18' }}>
            {roleLabel}
          </h2>
        </div>

        <button
          className="relative p-1.5 rounded hover:bg-black/5"
          aria-label="Notifications"
          data-testid="topbar-notifications"
        >
          <Bell className="w-[18px] h-[18px]" style={{ color: '#5F5E5A' }} />
        </button>

        <div className="avatar-circle">{initial}</div>
      </header>

      {/* ============ MOBILE DRAWER ============ */}
      {drawerOpen && (
        <>
          <div
            className="lg:hidden fixed inset-0 bg-black/50 z-40"
            onClick={() => setDrawerOpen(false)}
            data-testid="drawer-overlay"
          />
          <aside
            className="lg:hidden fixed top-0 left-0 z-50 h-screen w-64 flex flex-col"
            style={{ backgroundColor: '#0F172A' }}
            data-testid="mobile-drawer"
          >
            <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
              <div className="flex items-center gap-2.5">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: 'var(--accent-raw)' }}
                >
                  <Building2 className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="text-white font-medium text-[14px] leading-tight">SocietyHub</div>
                  <div className="text-[10px] uppercase tracking-wider mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    {roleLabel}
                  </div>
                </div>
              </div>
              <button onClick={() => setDrawerOpen(false)} className="p-1 rounded hover:bg-white/10">
                <X className="w-5 h-5 text-white" />
              </button>
            </div>

            <nav className="flex-1 px-3 py-3 overflow-y-auto scrollbar-thin space-y-0.5">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setDrawerOpen(false)}
                  data-testid={`drawer-nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                  className={`sidebar-item ${isActive(item.path) ? 'sidebar-item-active' : ''}`}
                >
                  <item.icon className="w-[18px] h-[18px]" />
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>

            <div className="px-3 py-3 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
              <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg mb-2" style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}>
                <div className="avatar-circle" style={{ width: 32, height: 32 }}>{initial}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-[12px] font-medium truncate">{user?.name}</p>
                  <p className="text-[10px] truncate" style={{ color: 'rgba(255,255,255,0.5)' }}>{user?.mobile}</p>
                </div>
              </div>
              {roles.length > 1 && (
                <div className="mb-2 space-y-1">
                  {roles.filter((r) => r.role !== role).map((r) => (
                    <button
                      key={r.role}
                      onClick={() => { handleRoleSwitch(r.role); setDrawerOpen(false); }}
                      data-testid={`drawer-switch-${r.role}`}
                      className="w-full text-left px-3 py-2 rounded-lg text-[12px]"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.85)' }}
                    >
                      Switch to {r.role.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </button>
                  ))}
                </div>
              )}
              <button
                onClick={handleLogout}
                data-testid="drawer-logout-btn"
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[12px]"
                style={{ backgroundColor: 'rgba(163,45,45,0.15)', color: '#FCA5A5' }}
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          </aside>
        </>
      )}

      {/* ============ MORE SHEET (mobile bottom nav overflow) ============ */}
      {moreOpen && (
        <>
          <div
            className="lg:hidden fixed inset-0 bg-black/40 z-40"
            onClick={() => setMoreOpen(false)}
            data-testid="more-sheet-overlay"
          />
          <div
            className="lg:hidden fixed left-0 right-0 bottom-0 z-50 rounded-t-2xl pt-3 pb-6"
            style={{ backgroundColor: '#FFFFFF', boxShadow: '0 -4px 20px rgba(0,0,0,0.10)' }}
            data-testid="more-sheet"
          >
            <div className="w-10 h-1 rounded-full mx-auto mb-3" style={{ backgroundColor: 'rgba(0,0,0,0.12)' }} />
            <div className="px-4 pb-2">
              <p className="text-[11px] uppercase tracking-wider font-medium" style={{ color: '#5F5E5A' }}>
                More options
              </p>
            </div>
            <div className="grid grid-cols-4 gap-2 px-4 pt-2">
              {moreItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMoreOpen(false)}
                  data-testid={`more-nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                  className="flex flex-col items-center gap-1.5 p-3 rounded-lg"
                  style={{
                    backgroundColor: isActive(item.path) ? 'var(--accent-light)' : 'transparent',
                    color: isActive(item.path) ? 'var(--accent-raw)' : '#1A1A18',
                  }}
                >
                  <item.icon className="w-5 h-5" />
                  <span className="text-[10px] text-center leading-tight">{item.label}</span>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}

      {/* ============ MAIN ============ */}
      <main
        className="lg:pl-60 pt-[52px] lg:pt-[56px] min-h-screen"
        style={{ paddingBottom: '72px' }}
        data-testid="main-content"
      >
        <div className="px-4 sm:px-6 py-4 sm:py-6 lg:pb-6">
          <div className="lg:hidden" style={{ paddingBottom: 0 }} />
          {children}
        </div>
      </main>

      {/* ============ MOBILE BOTTOM NAV ============ */}
      <nav
        className="lg:hidden fixed bottom-0 left-0 right-0 z-30 flex items-stretch"
        style={{
          height: 64,
          backgroundColor: '#FFFFFF',
          borderTop: '0.5px solid rgba(0,0,0,0.10)',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }}
        data-testid="bottom-nav"
      >
        {mobileItems.map((item) => {
          const active = isActive(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`bottom-nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
              className="flex-1 flex flex-col items-center justify-center gap-0.5 relative"
              style={{
                color: active ? 'var(--accent-raw)' : '#5F5E5A',
              }}
            >
              {active && (
                <span
                  className="absolute top-0 left-1/2 -translate-x-1/2 rounded-b-full"
                  style={{ width: 24, height: 2, backgroundColor: 'var(--accent-raw)' }}
                />
              )}
              <item.icon className="w-[20px] h-[20px]" strokeWidth={active ? 2.2 : 1.8} />
              <span className="text-[10px] font-medium leading-tight">{item.label}</span>
            </Link>
          );
        })}
        {moreItems.length > 0 && (
          <button
            onClick={() => setMoreOpen(true)}
            data-testid="bottom-nav-more"
            className="flex-1 flex flex-col items-center justify-center gap-0.5"
            style={{ color: moreOpen ? 'var(--accent-raw)' : '#5F5E5A' }}
          >
            <MoreHorizontal className="w-[20px] h-[20px]" strokeWidth={1.8} />
            <span className="text-[10px] font-medium leading-tight">More</span>
          </button>
        )}
      </nav>
    </div>
  );
};

export default RoleLayout;
