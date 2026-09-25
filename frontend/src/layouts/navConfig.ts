import type { Role } from "@/types/enums";

export interface NavItem {
  label: string;
  path: string;
  icon: "home" | "dues" | "complaint" | "visitor" | "notice" | "amenity" | "proposal" | "expense" | "people" | "wallet" | "todo" | "society" | "report";
}

/**
 * One nav set per role — Section 4 dual-role means the SAME account can see
 * a different set depending on `activeRole`, not a different account.
 */
export const navByRole: Record<Role, NavItem[]> = {
  PLATFORM_OWNER: [
    { label: "Societies", path: "/platform/societies", icon: "society" },
    { label: "Change Admin", path: "/platform/change-admin", icon: "people" },
    { label: "Reports", path: "/platform/reports", icon: "report" },
  ],
  ADMIN: [
    { label: "Overview", path: "/admin", icon: "home" },
    { label: "Residents", path: "/admin/residents", icon: "people" },
    { label: "Assign Sub-admin", path: "/admin/assign-subadmin", icon: "people" },
    { label: "Staff", path: "/admin/staff", icon: "people" },
    { label: "Properties", path: "/admin/properties", icon: "society" },
    { label: "MONTHLY MAINTENANCE", path: "/admin/dues", icon: "dues" },
    { label: "Complaints", path: "/admin/complaints", icon: "complaint" },
    { label: "Visitors", path: "/admin/visitors", icon: "visitor" },
    { label: "Notices", path: "/admin/notices", icon: "notice" },
    { label: "Amenities", path: "/admin/amenities", icon: "amenity" },
    { label: "Proposals", path: "/admin/proposals", icon: "proposal" },
    { label: "Expenses", path: "/admin/expense-bills", icon: "expense" },
    { label: "Accounts", path: "/admin/accounts", icon: "wallet" },
    { label: "Reports", path: "/admin/reports", icon: "report" },
  ],
  SUB_ADMIN: [
    { label: "Overview", path: "/subadmin", icon: "home" },
    { label: "MONTHLY MAINTENANCE", path: "/subadmin/dues", icon: "dues" },
    { label: "Complaints", path: "/subadmin/complaints", icon: "complaint" },
    { label: "Proposals", path: "/subadmin/proposals", icon: "proposal" },
    { label: "Expenses", path: "/subadmin/expense-bills", icon: "expense" },
    { label: "Reports", path: "/subadmin/reports", icon: "report" },
  ],
  MANAGER: [
    { label: "Overview", path: "/manager", icon: "home" },
    { label: "My To-Dos", path: "/manager/todos", icon: "todo" },
    { label: "Complaints", path: "/manager/complaints", icon: "complaint" },
    { label: "MONTHLY MAINTENANCE", path: "/manager/dues", icon: "dues" },
  ],
  RESIDENT: [
    { label: "Home", path: "/resident", icon: "home" },
    { label: "MONTHLY MAINTENANCE", path: "/resident/dues", icon: "dues" },
    { label: "Wallet", path: "/resident/wallet", icon: "wallet" },
    { label: "Complaints", path: "/resident/complaints", icon: "complaint" },
    { label: "Visitors", path: "/resident/visitors", icon: "visitor" },
    { label: "Notices", path: "/resident/notices", icon: "notice" },
    { label: "Amenities", path: "/resident/amenities", icon: "amenity" },
    { label: "Proposals", path: "/resident/proposals", icon: "proposal" },
    { label: "Reports", path: "/resident/reports", icon: "report" },
  ],
  SECURITY_GUARD: [
    { label: "Visitors", path: "/guard", icon: "visitor" },
  ],
};
