import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import type { Role } from "@/types/enums";

const roleLabels: Record<Role, string> = {
  PLATFORM_OWNER: "Platform Owner",
  ADMIN: "Admin",
  SUB_ADMIN: "Sub-admin",
  MANAGER: "Manager",
  RESIDENT: "Resident",
  SECURITY_GUARD: "Security Guard",
};

const homeByRole: Record<Role, string> = {
  PLATFORM_OWNER: "/platform/societies",
  ADMIN: "/admin",
  SUB_ADMIN: "/subadmin",
  MANAGER: "/manager",
  RESIDENT: "/resident",
  SECURITY_GUARD: "/guard",
};

/** Section 4.3: switching is a dashboard/context change only — same
 * account, same identity, never a second login. Only rendered when the
 * account genuinely has more than one active role available. */
export function RoleSwitcher() {
  const { activeRole, availableRoles, switchRole } = useAuth();
  const navigate = useNavigate();
  const [switching, setSwitching] = useState(false);

  if (availableRoles.length <= 1 || !activeRole) return null;

  async function handleSwitch(role: Role) {
    setSwitching(true);
    try {
      await switchRole(role);
      navigate(homeByRole[role]);
    } finally {
      setSwitching(false);
    }
  }

  // The only combination this app currently grants (ADMIN+RESIDENT,
  // SUB_ADMIN+RESIDENT) is exactly two roles — a single "Switch to X"
  // button reads better here than a dropdown with just one other option.
  if (availableRoles.length === 2) {
    const otherRole = availableRoles.find((r) => r !== activeRole)!;
    return (
      <button
        onClick={() => handleSwitch(otherRole)}
        disabled={switching}
        className="px-3 py-1.5 rounded text-sm font-medium border transition-colors disabled:opacity-60 border-white/30 text-white hover:bg-white/10 md:border-line md:text-navy md:bg-white md:hover:border-navy"
      >
        {switching ? "Switching…" : `Switch to ${roleLabels[otherRole]}`}
      </button>
    );
  }

  // 3+ roles isn't a combination anything in the app grants today, but
  // kept as a safe fallback — a dropdown scales better than a chain of
  // toggle buttons if that ever changes.
  return (
    <label className="flex items-center gap-2 text-sm text-white/90 md:text-navy">
      <span className="sr-only md:not-sr-only md:text-navy-muted">View as</span>
      <select
        value={activeRole}
        disabled={switching}
        onChange={(e) => void handleSwitch(e.target.value as Role)}
        className="bg-transparent md:bg-white md:border md:border-line rounded px-2 py-1 text-sm"
      >
        {availableRoles.map((role) => (
          <option key={role} value={role} className="text-ink">
            {roleLabels[role]}
          </option>
        ))}
      </select>
    </label>
  );
}
