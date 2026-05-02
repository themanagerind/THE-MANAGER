import {
  LayoutDashboard, Receipt, Wallet, BarChart3,
  Bell, MessageSquare, ShoppingBag,
} from 'lucide-react';
import RoleLayout from './RoleLayout';

const ResidentLayout = ({ children }) => {
  const navItems = [
    { path: '/resident', icon: LayoutDashboard, label: 'Home', mobile: true },
    { path: '/resident/bills', icon: Receipt, label: 'Bills', mobile: true },
    { path: '/resident/wallet', icon: Wallet, label: 'Wallet', mobile: true },
    { path: '/resident/bazaar', icon: ShoppingBag, label: 'Bazaar', mobile: true },
    { path: '/resident/reports', icon: BarChart3, label: 'Reports' },
    { path: '/resident/notices', icon: Bell, label: 'Notices' },
    { path: '/resident/complaints', icon: MessageSquare, label: 'Complaints' },
  ];

  return (
    <RoleLayout role="resident" roleLabel="Resident" navItems={navItems}>
      {children}
    </RoleLayout>
  );
};

export default ResidentLayout;
