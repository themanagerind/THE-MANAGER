import {
  Building2, LayoutDashboard, Users, ShoppingBag,
} from 'lucide-react';
import RoleLayout from './RoleLayout';

const PlatformLayout = ({ children }) => {
  const navItems = [
    { path: '/platform', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/platform/societies', icon: Building2, label: 'Societies' },
    { path: '/platform/admins', icon: Users, label: 'Admins' },
    { path: '/platform/settings', icon: ShoppingBag, label: 'Bazaar' },
  ];

  return (
    <RoleLayout role="platform_owner" roleLabel="Platform Owner" navItems={navItems}>
      {children}
    </RoleLayout>
  );
};

export default PlatformLayout;
