import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsApi, type ResidentNotificationOut } from "@/api/notifications";

/**
 * Resident-only bell icon — Phase 1 in-app notifications (user-
 * requested). No push, no polling: fetched once when the panel opens
 * (plus the unread badge on mount), matching this app's existing
 * fetch-on-navigate pattern rather than adding continuous polling
 * anywhere (see queryClient's 30s staleTime — no page in this app uses
 * refetchInterval).
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const countQuery = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => notificationsApi.unreadCount().then((r) => r.data.count),
  });

  const listQuery = useQuery({
    queryKey: ["notifications", "mine"],
    queryFn: () => notificationsApi.mine().then((r) => r.data),
    enabled: open,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  function handleClickNotification(n: ResidentNotificationOut) {
    if (!n.is_read) markRead.mutate(n.id);
    setOpen(false);
    navigate("/resident/dues");
  }

  const count = countQuery.data ?? 0;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="Notifications"
        onClick={() => setOpen((v) => !v)}
        className="relative w-8 h-8 rounded-full flex items-center justify-center text-white/80 hover:text-white hover:bg-white/10 md:text-navy-muted md:hover:text-navy md:hover:bg-navy/5"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5" aria-hidden="true">
          <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-danger text-white text-[10px] leading-4 text-center font-medium">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-80 max-w-[90vw] bg-white text-ink border border-line rounded shadow-lg z-20">
            <div className="flex items-center justify-between px-3 py-2 border-b border-line">
              <span className="text-sm font-medium text-navy">Notifications</span>
              {count > 0 && (
                <button
                  type="button"
                  onClick={() => markAllRead.mutate()}
                  className="text-xs text-navy underline"
                >
                  Mark all read
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {listQuery.isLoading && <p className="px-3 py-3 text-xs text-navy-muted">Loading…</p>}
              {listQuery.data && listQuery.data.items.length === 0 && (
                <p className="px-3 py-3 text-xs text-navy-muted">No notifications yet.</p>
              )}
              {listQuery.data?.items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleClickNotification(n)}
                  className={`w-full text-left px-3 py-2 text-sm border-b border-line last:border-b-0 hover:bg-paper ${
                    n.is_read ? "text-navy-muted" : "text-ink font-medium"
                  }`}
                >
                  <p>{n.title}</p>
                  <p className="text-xs font-normal text-navy-muted mt-0.5">{n.message}</p>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
