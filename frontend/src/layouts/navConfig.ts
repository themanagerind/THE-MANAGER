import type { Role } from "@/types/enums";

export interface NavItem {
  label: string;
  path: string;
  icon: "home" | "dues" | "complaint" | "visitor" | "notice" | "amenity" | "proposal" | "expense" | "people" | "wallet" | "todo" | "society";
}

/**
 * One nav set per role — Section 4 dual-role means the SAME account can see
 * a different set depending on `activeRole`, not a different account.
 */
export const navByRole: Record<Role, NavItem[]> = {
  PLATFORM_OWNER: [
    { label: "Societies", path: "/platform/societies", icon: "society" },
  ],
  ADMIN: [
    { label: "Overview", path: "/admin", icon: "home" },
    { label: "Residents", path: "/admin/residents", icon: "people" },
    { label: "Properties", path: "/admin/properties", icon: "society" },
    { label: "Dues", path: "/admin/dues", icon: "dues" },
    { label: "Complaints", path: "/admin/complaints", icon: "complaint" },
    { label: "Visitors", path: "/admin/visitors", icon: "visitor" },
    { label: "Notices", path: "/admin/notices", icon: "notice" },
    { label: "Amenities", path: "/admin/amenities", icon: "amenity" },
    { label: "Proposals", path: "/admin/proposals", icon: "proposal" },
    { label: "Expenses", path: "/admin/expense-bills", icon: "expense" },
    { label: "Accounts", path: "/admin/accounts", icon: "wallet" },
  ],
  SUB_ADMIN: [
    { label: "Overview", path: "/subadmin", icon: "home" },
    { label: "Dues", path: "/subadmin/dues", icon: "dues" },
    { label: "Complaints", path: "/subadmin/complaints", icon: "complaint" },
    { label: "Proposals", path: "/subadmin/proposals", icon: "proposal" },
    { label: "Expenses", path: "/subadmin/expense-bills", icon: "expense" },
  ],
  MANAGER: [
    { label: "Overview", path: "/manager", icon: "home" },
    { label: "My To-Dos", path: "/manager/todos", icon: "todo" },
    { label: "Complaints", path: "/manager/complaints", icon: "complaint" },
    { label: "Dues", path: "/manager/dues", icon: "dues" },
  ],
  RESIDENT: [
    { label: "Home", path: "/resident", icon: "home" },
    { label: "Dues", path: "/resident/dues", icon: "dues" },
    { label: "Wallet", path: "/resident/wallet", icon: "wallet" },
    { label: "Complaints", path: "/resident/complaints", icon: "complaint" },
    { label: "Visitors", path: "/resident/visitors", icon: "visitor" },
    { label: "Notices", path: "/resident/notices", icon: "notice" },
    { label: "Amenities", path: "/resident/amenities", icon: "amenity" },
    { label: "Proposals", path: "/resident/proposals", icon: "proposal" },
  ],
  SECURITY_GUARD: [
    { label: "Visitors", path: "/guard", icon: "visitor" },
  ],
};
