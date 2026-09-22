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

  if (availableRoles.length <= 1 || !activeRole) return null;

  return (
    <label className="flex items-center gap-2 text-sm text-white/90 md:text-navy">
      <span className="sr-only md:not-sr-only md:text-navy-muted">View as</span>
      <select
        value={activeRole}
        onChange={async (e) => {
          const role = e.target.value as Role;
          await switchRole(role);
          navigate(homeByRole[role]);
        }}
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
