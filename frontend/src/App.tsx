import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { AppShell } from "@/layouts/AppShell";
import { Login } from "@/pages/Login";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { ResidentDashboard } from "@/pages/resident/Dashboard";
import { ResidentDues } from "@/pages/resident/Dues";
import { ResidentWallet } from "@/pages/resident/Wallet";
import { ResidentComplaints } from "@/pages/resident/Complaints";
import { ResidentVisitors } from "@/pages/resident/Visitors";
import { ResidentNotices } from "@/pages/resident/Notices";
import { ResidentAmenities } from "@/pages/resident/Amenities";
import { ResidentProposals } from "@/pages/resident/Proposals";
import { AdminOverview } from "@/pages/admin/Overview";
import { AdminResidents } from "@/pages/admin/Residents";
import { AdminProperties } from "@/pages/admin/Properties";
import { AdminDues } from "@/pages/admin/Dues";
import { ManagerTodos } from "@/pages/manager/Todos";
import { ManagerComplaints } from "@/pages/manager/Complaints";

function RoleHomeRedirect() {
  const { activeRole } = useAuth();
  const homeByRole: Record<string, string> = {
    PLATFORM_OWNER: "/platform/societies",
    ADMIN: "/admin",
    SUB_ADMIN: "/subadmin",
    MANAGER: "/manager",
    RESIDENT: "/resident",
    SECURITY_GUARD: "/guard",
  };
  return <Navigate to={activeRole ? homeByRole[activeRole] : "/login"} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<RoleHomeRedirect />} />

          <Route element={<ProtectedRoute allow={["PLATFORM_OWNER"]} />}>
            <Route path="/platform/societies" element={<PlaceholderPage title="Societies" />} />
          </Route>

          <Route element={<ProtectedRoute allow={["ADMIN"]} />}>
            <Route path="/admin" element={<AdminOverview />} />
            <Route path="/admin/residents" element={<AdminResidents />} />
            <Route path="/admin/properties" element={<AdminProperties />} />
            <Route path="/admin/dues" element={<AdminDues />} />
            <Route path="/admin/complaints" element={<PlaceholderPage title="Complaints" />} />
            <Route path="/admin/visitors" element={<PlaceholderPage title="Visitors" />} />
            <Route path="/admin/notices" element={<PlaceholderPage title="Notices" />} />
            <Route path="/admin/amenities" element={<PlaceholderPage title="Amenities" />} />
            <Route path="/admin/proposals" element={<PlaceholderPage title="Proposals" />} />
            <Route path="/admin/expense-bills" element={<PlaceholderPage title="Expense Bills" />} />
            <Route path="/admin/accounts" element={<PlaceholderPage title="Accounts" />} />
          </Route>

          <Route element={<ProtectedRoute allow={["SUB_ADMIN"]} />}>
            <Route path="/subadmin" element={<PlaceholderPage title="Overview" />} />
            <Route path="/subadmin/dues" element={<PlaceholderPage title="Maintenance Dues" />} />
            <Route path="/subadmin/complaints" element={<PlaceholderPage title="Complaints" />} />
            <Route path="/subadmin/proposals" element={<PlaceholderPage title="Proposals" />} />
            <Route path="/subadmin/expense-bills" element={<PlaceholderPage title="Expense Bills" />} />
          </Route>

          <Route element={<ProtectedRoute allow={["MANAGER"]} />}>
            <Route path="/manager" element={<ManagerTodos />} />
            <Route path="/manager/complaints" element={<ManagerComplaints />} />
          </Route>

          <Route element={<ProtectedRoute allow={["RESIDENT"]} />}>
            <Route path="/resident" element={<ResidentDashboard />} />
            <Route path="/resident/dues" element={<ResidentDues />} />
            <Route path="/resident/wallet" element={<ResidentWallet />} />
            <Route path="/resident/complaints" element={<ResidentComplaints />} />
            <Route path="/resident/visitors" element={<ResidentVisitors />} />
            <Route path="/resident/notices" element={<ResidentNotices />} />
            <Route path="/resident/amenities" element={<ResidentAmenities />} />
            <Route path="/resident/proposals" element={<ResidentProposals />} />
          </Route>

          <Route element={<ProtectedRoute allow={["SECURITY_GUARD"]} />}>
            <Route path="/guard" element={<PlaceholderPage title="Visitors" />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<PlaceholderPage title="Page not found" />} />
    </Routes>
  );
}
