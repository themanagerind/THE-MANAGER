import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import useAuthStore from './store/authStore';

// Auth Pages
import { Login, Register } from './pages/auth/AuthPages';

// Layouts
import PlatformLayout from './components/layout/PlatformLayout';
import AdminLayout from './components/layout/AdminLayout';
import SubAdminLayout from './components/layout/SubAdminLayout';
import ResidentLayout from './components/layout/ResidentLayout';

// Platform Owner Pages
import { PlatformDashboard, ManageAdmins, BazaarSettings } from './pages/platform/PlatformPages';

// Admin Pages
import { AdminDashboard, WingsManager, FlatMapping, ResidentsManager } from './pages/admin/AdminPages';
import MaintenanceBills from './pages/admin/MaintenanceBills';
import IncomePage from './pages/admin/IncomePage';
import ExpensesPage from './pages/admin/ExpensesPage';
import PlansPage from './pages/admin/PlansPage';

// Sub-Admin Pages
import { SubAdminDashboard, VerifyPayments, PlanApprovals, ExpenseApprovals } from './pages/subadmin/SubAdminPages';

// Resident Pages
import { ResidentDashboard, MyBills, WalletPage } from './pages/resident/ResidentPages';

// Shared Pages
import ReportsPage from './pages/shared/ReportsPage';
import { NoticesPage, ComplaintsPage, BazaarPage } from './pages/shared/SharedPages';


// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { isAuthenticated, user } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    // Redirect to appropriate dashboard
    switch (user?.role) {
      case 'platform_owner':
        return <Navigate to="/platform" replace />;
      case 'admin':
        return <Navigate to="/admin" replace />;
      case 'sub_admin':
        return <Navigate to="/subadmin" replace />;
      case 'resident':
        return <Navigate to="/resident" replace />;
      default:
        return <Navigate to="/login" replace />;
    }
  }
  
  return children;
};

// Home redirect based on role
const HomeRedirect = () => {
  const { isAuthenticated, user } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  switch (user?.role) {
    case 'platform_owner':
      return <Navigate to="/platform" replace />;
    case 'admin':
      return <Navigate to="/admin" replace />;
    case 'sub_admin':
      return <Navigate to="/subadmin" replace />;
    case 'resident':
      return <Navigate to="/resident" replace />;
    default:
      return <Navigate to="/login" replace />;
  }
};

function App() {
  return (
    <>
      <Toaster 
        position="top-right" 
        richColors 
        theme="dark"
        toastOptions={{
          style: {
            background: '#1A2B3C',
            border: '1px solid #2E4057',
            color: '#ECF0F1',
          },
        }}
      />
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Home Redirect */}
          <Route path="/" element={<HomeRedirect />} />
          
          {/* Platform Owner Routes */}
          <Route
            path="/platform"
            element={
              <ProtectedRoute allowedRoles={['platform_owner']}>
                <PlatformLayout>
                  <PlatformDashboard />
                </PlatformLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/platform/admins"
            element={
              <ProtectedRoute allowedRoles={['platform_owner']}>
                <PlatformLayout>
                  <ManageAdmins />
                </PlatformLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/platform/settings"
            element={
              <ProtectedRoute allowedRoles={['platform_owner']}>
                <PlatformLayout>
                  <BazaarSettings />
                </PlatformLayout>
              </ProtectedRoute>
            }
          />
          
          {/* Admin Routes */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <AdminDashboard />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/wings"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <WingsManager />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/flats"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <FlatMapping />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/residents"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <ResidentsManager />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/maintenance"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <MaintenanceBills />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/income"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <IncomePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/expenses"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <ExpensesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/plans"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <PlansPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/reports"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <ReportsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/notices"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <NoticesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/complaints"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminLayout>
                  <ComplaintsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          
          {/* Sub-Admin Routes */}
          <Route
            path="/subadmin"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <SubAdminDashboard />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/payments"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <VerifyPayments />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/plans"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <PlanApprovals />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/expenses"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <ExpenseApprovals />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/wallet"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <WalletPage />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/reports"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <ReportsPage />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/notices"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <NoticesPage />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/subadmin/complaints"
            element={
              <ProtectedRoute allowedRoles={['sub_admin']}>
                <SubAdminLayout>
                  <ComplaintsPage />
                </SubAdminLayout>
              </ProtectedRoute>
            }
          />
          
          {/* Resident Routes */}
          <Route
            path="/resident"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <ResidentDashboard />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/resident/bills"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <MyBills />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/resident/wallet"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <WalletPage />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/resident/reports"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <ReportsPage />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/resident/notices"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <NoticesPage />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/resident/complaints"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <ComplaintsPage />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/resident/bazaar"
            element={
              <ProtectedRoute allowedRoles={['resident']}>
                <ResidentLayout>
                  <BazaarPage />
                </ResidentLayout>
              </ProtectedRoute>
            }
          />
          
          {/* Catch all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
