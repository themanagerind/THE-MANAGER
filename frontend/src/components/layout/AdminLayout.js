import {
  Building2, LayoutDashboard, Home, Users, Receipt, FileText,
  ClipboardList, Bell, MessageSquare, BarChart3,
} from 'lucide-react';
import RoleLayout from './RoleLayout';

const AdminLayout = ({ children }) => {
  const navItems = [
    { path: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/admin/maintenance', icon: Receipt, label: 'Bills' },
    { path: '/admin/residents', icon: Users, label: 'Residents' },
    { path: '/admin/reports', icon: BarChart3, label: 'Reports' },
    // overflow (More)
    { path: '/admin/wings', icon: Building2, label: 'Wings' },
    { path: '/admin/flats', icon: Home, label: 'Flats' },
    { path: '/admin/income', icon: BarChart3, label: 'Income' },
    { path: '/admin/expenses', icon: FileText, label: 'Expenses' },
    { path: '/admin/plans', icon: ClipboardList, label: 'Plans' },
    { path: '/admin/notices', icon: Bell, label: 'Notices' },
    { path: '/admin/complaints', icon: MessageSquare, label: 'Complaints' },
  ];

  // Mobile bottom nav: first 4 with mobile:true
  const navWithMobile = navItems.map((item, i) => ({ ...item, mobile: i < 4 }));

  return (
    <RoleLayout role="admin" roleLabel="Admin" navItems={navWithMobile}>
      {children}
    </RoleLayout>
  );
};

export default AdminLayout;
