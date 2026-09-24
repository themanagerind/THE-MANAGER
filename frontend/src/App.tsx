import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { AppShell } from "@/layouts/AppShell";
import { Login } from "@/pages/Login";
import { Signup } from "@/pages/Signup";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { PlatformSocieties } from "@/pages/platform/Societies";
import { PlatformReports } from "@/pages/platform/Reports";
import { SocietyMapping } from "@/pages/platform/SocietyMapping";
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
import { AssignSubAdmin } from "@/pages/admin/AssignSubAdmin";
import { AdminProperties } from "@/pages/admin/Properties";
import { AdminDues } from "@/pages/admin/Dues";
import { AdminComplaints } from "@/pages/admin/Complaints";
import { AdminVisitors } from "@/pages/admin/Visitors";
import { AdminNotices } from "@/pages/admin/Notices";
import { AdminAmenities } from "@/pages/admin/Amenities";
import { AdminProposals } from "@/pages/admin/Proposals";
import { AdminExpenseBills } from "@/pages/admin/ExpenseBills";
import { AdminAccounts } from "@/pages/admin/Accounts";
import { ManagerOverview } from "@/pages/manager/Overview";
import { ManagerTodos } from "@/pages/manager/Todos";
import { ManagerComplaints } from "@/pages/manager/Complaints";
import { ManagerDues } from "@/pages/manager/Dues";
import { SubAdminOverview } from "@/pages/subadmin/Overview";
import { SubAdminDues } from "@/pages/subadmin/Dues";
import { SubAdminExpenseBills } from "@/pages/subadmin/ExpenseBills";
import { GuardVisitors } from "@/pages/guard/Visitors";
import { Profile } from "@/pages/Profile";

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
      <Route path="/signup" element={<Signup />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<RoleHomeRedirect />} />
          <Route path="/profile" element={<Profile />} />

          <Route element={<ProtectedRoute allow={["PLATFORM_OWNER"]} />}>
            <Route path="/platform/societies" element={<PlatformSocieties />} />
            <Route path="/platform/societies/:societyId/mapping" element={<SocietyMapping />} />
            <Route path="/platform/reports" element={<PlatformReports />} />
          </Route>

          <Route element={<ProtectedRoute allow={["ADMIN"]} />}>
            <Route path="/admin" element={<AdminOverview />} />
            <Route path="/admin/residents" element={<AdminResidents />} />
            <Route path="/admin/assign-subadmin" element={<AssignSubAdmin />} />
            <Route path="/admin/properties" element={<AdminProperties />} />
            <Route path="/admin/dues" element={<AdminDues />} />
            <Route path="/admin/complaints" element={<AdminComplaints />} />
            <Route path="/admin/visitors" element={<AdminVisitors />} />
            <Route path="/admin/notices" element={<AdminNotices />} />
            <Route path="/admin/amenities" element={<AdminAmenities />} />
            <Route path="/admin/proposals" element={<AdminProposals />} />
            <Route path="/admin/expense-bills" element={<AdminExpenseBills />} />
            <Route path="/admin/accounts" element={<AdminAccounts />} />
          </Route>

          <Route element={<ProtectedRoute allow={["SUB_ADMIN"]} />}>
            <Route path="/subadmin" element={<SubAdminOverview />} />
            <Route path="/subadmin/dues" element={<SubAdminDues />} />
            {/* Same component as Admin's — the backend already scopes list/
                assign/status-update results to the Sub-admin's Wing/Row,
                and the UI has no Admin-only actions to hide. */}
            <Route path="/subadmin/complaints" element={<AdminComplaints />} />
            {/* Same component as Resident's — both only list and vote;
                raising/withdrawing a proposal is Admin-only and isn't
                rendered here either way. */}
            <Route path="/subadmin/proposals" element={<ResidentProposals />} />
            <Route path="/subadmin/expense-bills" element={<SubAdminExpenseBills />} />
          </Route>

          <Route element={<ProtectedRoute allow={["MANAGER"]} />}>
            <Route path="/manager" element={<ManagerOverview />} />
            <Route path="/manager/todos" element={<ManagerTodos />} />
            <Route path="/manager/complaints" element={<ManagerComplaints />} />
            <Route path="/manager/dues" element={<ManagerDues />} />
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
            <Route path="/guard" element={<GuardVisitors />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<PlaceholderPage title="Page not found" />} />
    </Routes>
  );
}
