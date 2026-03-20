import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  Building2, LayoutDashboard, Receipt, Wallet, BarChart3,
  Bell, MessageSquare, ShoppingBag, LogOut, Menu, X, ChevronDown
} from 'lucide-react';
import useAuthStore from '../../store/authStore';
import { authAPI } from '../../lib/api';
import { toast } from 'sonner';

const ResidentLayout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, switchRole } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [roles, setRoles] = useState([]);
  const [showRoleSwitch, setShowRoleSwitch] = useState(false);

  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const res = await authAPI.getRoles();
        setRoles(res.data);
      } catch (e) {
        console.error('Failed to fetch roles');
      }
    };
    fetchRoles();
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
    toast.success('Logged out successfully');
  };

  const handleRoleSwitch = async (role) => {
    try {
      const res = await authAPI.switchRole(role);
      switchRole(res.data.user, res.data.access_token);
      toast.success(`Switched to ${role} role`);
      
      switch (role) {
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

  const navItems = [
    { path: '/resident', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/resident/bills', icon: Receipt, label: 'My Bills' },
    { path: '/resident/wallet', icon: Wallet, label: 'Wallet' },
    { path: '/resident/reports', icon: BarChart3, label: 'Reports' },
    { path: '/resident/notices', icon: Bell, label: 'Notices' },
    { path: '/resident/complaints', icon: MessageSquare, label: 'Complaints' },
    { path: '/resident/bazaar', icon: ShoppingBag, label: 'Bazaar' },
  ];

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen bg-bg-base">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-bg-surface border-b border-border-color h-16 flex items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setSidebarOpen(true)}
            className="p-2 hover:bg-bg-elevated rounded-lg"
            data-testid="mobile-menu-btn"
          >
            <Menu className="w-6 h-6 text-text-primary" />
          </button>
          <div className="flex items-center gap-2">
            <Building2 className="w-6 h-6 text-accent" />
            <span className="font-semibold text-text-primary">Resident</span>
          </div>
        </div>
      </div>

      {/* Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 z-50 h-screen w-60 bg-bg-surface border-r border-border-color
        transform transition-transform duration-300 ease-in-out
        lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-border-color">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-accent/20 rounded-lg">
                  <Building2 className="w-6 h-6 text-accent" />
                </div>
                <span className="text-lg font-bold text-text-primary">SocietyHub</span>
              </div>
              <button 
                onClick={() => setSidebarOpen(false)}
                className="lg:hidden p-1 hover:bg-bg-elevated rounded"
              >
                <X className="w-5 h-5 text-text-secondary" />
              </button>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto scrollbar-thin">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                onClick={() => setSidebarOpen(false)}
                className={`sidebar-item ${isActive(item.path) ? 'sidebar-item-active' : ''}`}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>

          {/* User Section */}
          <div className="p-4 border-t border-border-color">
            {roles.length > 1 && (
              <div className="mb-3 relative">
                <button
                  onClick={() => setShowRoleSwitch(!showRoleSwitch)}
                  data-testid="role-switch-btn"
                  className="w-full flex items-center justify-between px-3 py-2 bg-bg-elevated rounded-lg text-sm text-text-secondary hover:text-text-primary"
                >
                  <span>Switch Role</span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${showRoleSwitch ? 'rotate-180' : ''}`} />
                </button>
                {showRoleSwitch && (
                  <div className="absolute bottom-full left-0 right-0 mb-1 bg-bg-elevated rounded-lg border border-border-color shadow-lg overflow-hidden">
                    {roles.map((r) => (
                      <button
                        key={r.role}
                        onClick={() => handleRoleSwitch(r.role)}
                        data-testid={`switch-to-${r.role}`}
                        className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-bg-surface hover:text-text-primary"
                      >
                        {r.role.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center">
                <span className="text-accent font-semibold">
                  {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">{user?.name}</p>
                <p className="text-xs text-text-secondary truncate">{user?.mobile}</p>
              </div>
            </div>
            
            <button
              onClick={handleLogout}
              data-testid="logout-btn"
              className="w-full flex items-center gap-2 px-3 py-2 text-danger hover:bg-danger/10 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:pl-60 pt-16 lg:pt-0 min-h-screen">
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
};

export default ResidentLayout;
