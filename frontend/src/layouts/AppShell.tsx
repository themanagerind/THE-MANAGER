import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthContext";
import { navByRole } from "@/layouts/navConfig";
import { usersApi } from "@/api/users";
import { societiesApi } from "@/api/societies";
import { Icon } from "@/components/Icon";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import { OfflineQueueBanner } from "@/components/OfflineQueueBanner";
import { AuthenticatedImage } from "@/components/AuthenticatedImage";

const roleLabels: Record<string, string> = {
  PLATFORM_OWNER: "Platform Owner",
  ADMIN: "Admin",
  SUB_ADMIN: "Sub-admin",
  MANAGER: "Manager",
  RESIDENT: "Resident",
  SECURITY_GUARD: "Security Guard",
};

/** Roles that can upload their own photo (backend 403s everyone else on
 * POST /users/me/avatar) — shown in place of the default logo. */
const AVATAR_ROLES = new Set(["RESIDENT", "ADMIN", "SUB_ADMIN"]);

/** Sidebar header identity — Resident/Admin/Sub-admin/Manager/Platform
 * Owner see their own name; Security Guard sees the society's name
 * instead (a gate's identity is the society it guards, not the
 * individual guard on duty). */
function useHeaderIdentity(activeRole: string | null) {
  const isGuard = activeRole === "SECURITY_GUARD";
  const profileQuery = useQuery({
    queryKey: ["appshell", "profile"],
    queryFn: () => usersApi.me().then((r) => r.data),
    enabled: !!activeRole && !isGuard,
  });
  const societyQuery = useQuery({
    queryKey: ["appshell", "society-me"],
    queryFn: () => societiesApi.me().then((r) => r.data),
    enabled: isGuard,
  });

  const label = isGuard
    ? societyQuery.data?.name ?? "Society Manager"
    : profileQuery.data?.full_name ?? (activeRole ? roleLabels[activeRole] : "Society Manager");
  const hasAvatar = !isGuard && !!activeRole && AVATAR_ROLES.has(activeRole) && !!profileQuery.data?.has_avatar;

  return { label, hasAvatar };
}

export function AppShell() {
  const { activeRole, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const items = activeRole ? navByRole[activeRole] : [];
  const { label: headerLabel, hasAvatar } = useHeaderIdentity(activeRole);

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-paper">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col bg-navy text-white">
        <div className="px-6 py-5 border-b border-white/10 flex items-center gap-3">
          {hasAvatar ? (
            <AuthenticatedImage
              src="/users/me/avatar"
              alt=""
              className="w-9 h-9 rounded-full bg-white/5 object-cover shrink-0"
              fallback={<img src="/logo.png" alt="" className="w-9 h-9 rounded-full bg-white/5 object-cover shrink-0" />}
            />
          ) : (
            <img src="/logo.png" alt="" className="w-9 h-9 rounded-full bg-white/5 object-cover shrink-0" />
          )}
          <span className="text-lg font-semibold tracking-tight truncate">{headerLabel}</span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                  isActive ? "bg-white/10 text-white" : "text-white/70 hover:text-white hover:bg-white/5"
                }`
              }
              end
            >
              <Icon name={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-4 border-t border-white/10 space-y-1">
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `block px-3 py-2 rounded text-sm transition-colors ${
                isActive ? "bg-white/10 text-white" : "text-white/70 hover:text-white hover:bg-white/5"
              }`
            }
          >
            My Profile
          </NavLink>
          <button onClick={() => void logout()} className="w-full text-left px-3 py-2 rounded text-sm text-white/70 hover:text-white hover:bg-white/5">
            Log out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden sticky top-0 z-10 flex items-center justify-between bg-navy text-white px-4 py-3">
        <div className="flex items-center gap-2 min-w-0">
          {hasAvatar ? (
            <AuthenticatedImage
              src="/users/me/avatar"
              alt=""
              className="w-7 h-7 rounded-full bg-white/5 object-cover shrink-0"
              fallback={<img src="/logo.png" alt="" className="w-7 h-7 rounded-full bg-white/5 object-cover shrink-0" />}
            />
          ) : (
            <img src="/logo.png" alt="" className="w-7 h-7 rounded-full bg-white/5 object-cover shrink-0" />
          )}
          <span className="font-semibold truncate">{headerLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          {activeRole && <span className="text-xs text-white/70">{roleLabels[activeRole]}</span>}
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Account menu"
            className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-sm"
          >
            ⋮
          </button>
        </div>
      </header>
      {menuOpen && (
        <div className="md:hidden bg-navy-light text-white px-4 py-3 space-y-3">
          <RoleSwitcher />
          <NavLink to="/profile" onClick={() => setMenuOpen(false)} className="block text-sm text-white/80">
            My Profile
          </NavLink>
          <button onClick={() => void logout()} className="text-sm text-white/80">
            Log out
          </button>
        </div>
      )}

      <div className="hidden md:flex md:absolute md:top-5 md:right-6">
        <RoleSwitcher />
      </div>

      <main className="flex-1 pb-20 md:pb-0 px-4 py-5 md:px-8 md:py-8 max-w-5xl mx-auto w-full">
        <Outlet />
      </main>

      {/* Mobile bottom tabs */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-line flex justify-around py-2 z-10">
        {items.slice(0, 5).map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-2 py-1 text-[11px] ${isActive ? "text-navy" : "text-navy-muted"}`
            }
          >
            <Icon name={item.icon} className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <OfflineQueueBanner />
    </div>
  );
}
