import type { Role } from "@/types/enums";

export interface NavItem {
  // i18next key under the "nav" namespace (src/i18n/locales/*.json) —
  // AppShell resolves this via t(`nav.${labelKey}`), not a hardcoded string,
  // so the sidebar/bottom-tabs translate with the rest of the dashboard chrome.
  labelKey: string;
  path: string;
  icon: "home" | "dues" | "complaint" | "visitor" | "notice" | "amenity" | "proposal" | "expense" | "people" | "wallet" | "todo" | "society" | "report";
}

/**
 * One nav set per role — Section 4 dual-role means the SAME account can see
 * a different set depending on `activeRole`, not a different account.
 */
export const navByRole: Record<Role, NavItem[]> = {
  PLATFORM_OWNER: [
    { labelKey: "societies", path: "/platform/societies", icon: "society" },
    { labelKey: "changeAdmin", path: "/platform/change-admin", icon: "people" },
    { labelKey: "reports", path: "/platform/reports", icon: "report" },
  ],
  ADMIN: [
    { labelKey: "overview", path: "/admin", icon: "home" },
    { labelKey: "residents", path: "/admin/residents", icon: "people" },
    { labelKey: "assignSubAdmin", path: "/admin/assign-subadmin", icon: "people" },
    { labelKey: "staff", path: "/admin/staff", icon: "people" },
    { labelKey: "properties", path: "/admin/properties", icon: "society" },
    { labelKey: "monthlyMaintenance", path: "/admin/dues", icon: "dues" },
    { labelKey: "complaints", path: "/admin/complaints", icon: "complaint" },
    { labelKey: "visitors", path: "/admin/visitors", icon: "visitor" },
    { labelKey: "notices", path: "/admin/notices", icon: "notice" },
    { labelKey: "amenities", path: "/admin/amenities", icon: "amenity" },
    { labelKey: "proposals", path: "/admin/proposals", icon: "proposal" },
    { labelKey: "expenseApproval", path: "/admin/expense-bills", icon: "expense" },
    { labelKey: "accounts", path: "/admin/accounts", icon: "wallet" },
    { labelKey: "reports", path: "/admin/reports", icon: "report" },
  ],
  SUB_ADMIN: [
    { labelKey: "overview", path: "/subadmin", icon: "home" },
    { labelKey: "monthlyMaintenance", path: "/subadmin/dues", icon: "dues" },
    { labelKey: "complaints", path: "/subadmin/complaints", icon: "complaint" },
    { labelKey: "proposals", path: "/subadmin/proposals", icon: "proposal" },
    { labelKey: "expenseApproval", path: "/subadmin/expense-bills", icon: "expense" },
    { labelKey: "reports", path: "/subadmin/reports", icon: "report" },
  ],
  MANAGER: [
    { labelKey: "overview", path: "/manager", icon: "home" },
    { labelKey: "myTodos", path: "/manager/todos", icon: "todo" },
    { labelKey: "complaints", path: "/manager/complaints", icon: "complaint" },
    { labelKey: "monthlyMaintenance", path: "/manager/dues", icon: "dues" },
  ],
  RESIDENT: [
    { labelKey: "home", path: "/resident", icon: "home" },
    { labelKey: "monthlyMaintenance", path: "/resident/dues", icon: "dues" },
    { labelKey: "wallet", path: "/resident/wallet", icon: "wallet" },
    { labelKey: "complaints", path: "/resident/complaints", icon: "complaint" },
    { labelKey: "visitors", path: "/resident/visitors", icon: "visitor" },
    { labelKey: "notices", path: "/resident/notices", icon: "notice" },
    { labelKey: "amenities", path: "/resident/amenities", icon: "amenity" },
    { labelKey: "proposals", path: "/resident/proposals", icon: "proposal" },
    { labelKey: "reports", path: "/resident/reports", icon: "report" },
  ],
  SECURITY_GUARD: [
    { labelKey: "visitors", path: "/guard", icon: "visitor" },
  ],
};
