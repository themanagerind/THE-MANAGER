import {
  LayoutDashboard, CreditCard, FileText, ClipboardCheck,
  BarChart3, Bell, MessageSquare, Wallet,
} from 'lucide-react';
import RoleLayout from './RoleLayout';

const SubAdminLayout = ({ children }) => {
  const navItems = [
    { path: '/subadmin', icon: LayoutDashboard, label: 'Dashboard', mobile: true },
    { path: '/subadmin/payments', icon: CreditCard, label: 'Payments', mobile: true },
    { path: '/subadmin/expenses', icon: FileText, label: 'Expenses', mobile: true },
    { path: '/subadmin/reports', icon: BarChart3, label: 'Reports', mobile: true },
    { path: '/subadmin/plans', icon: ClipboardCheck, label: 'Plans' },
    { path: '/subadmin/wallet', icon: Wallet, label: 'Wallet' },
    { path: '/subadmin/notices', icon: Bell, label: 'Notices' },
    { path: '/subadmin/complaints', icon: MessageSquare, label: 'Complaints' },
  ];

  return (
    <RoleLayout role="sub_admin" roleLabel="Sub-Admin" navItems={navItems}>
      {children}
    </RoleLayout>
  );
};

export default SubAdminLayout;
