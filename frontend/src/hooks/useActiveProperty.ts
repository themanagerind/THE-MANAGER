import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { propertiesApi } from "@/api/properties";
import { useAuth } from "@/auth/AuthContext";

/** Audit #17: a bare "hs_active_property_id" key was shared across every
 * account on the device — on a shared device, or when switching between
 * multiple accounts under the same mobile number (Section 2.1), User B
 * could inherit User A's last-chosen property until the validity check in
 * the effect below happened to catch it. Namespacing by userId+societyId
 * makes that a non-issue: each identity gets its own stored choice. */
function activePropertyKey(userId: string | null, societyId: string | null): string | null {
  if (!userId) return null;
  return `hs_active_property_id:${societyId ?? "none"}:${userId}`;
}

/** Section 12: fetches every property the current Resident is actively
 * linked to (Owner or Tenant) — via the resident-scoped GET /properties
 * (backend fix) for house_number/floor labels, joined with the
 * relationship-type link from GET /residents/{id}/properties — and tracks
 * which one is "active" for screens that need a single property in
 * context (dues, complaints, visitors, amenity bookings). Persisted so
 * the choice survives reloads. */
export function useActiveProperty() {
  const { userId, societyId } = useAuth();
  const storageKey = activePropertyKey(userId, societyId);
  const [activePropertyId, setActivePropertyIdState] = useState<string | null>(
    () => (storageKey ? localStorage.getItem(storageKey) : null)
  );

  // Identity changed (e.g. switched accounts) — drop whatever was loaded
  // for the previous identity's storage key until the new one resolves.
  useEffect(() => {
    setActivePropertyIdState(storageKey ? localStorage.getItem(storageKey) : null);
  }, [storageKey]);

  const linksQuery = useQuery({
    queryKey: ["resident-property-links", userId],
    queryFn: () => propertiesApi.myLinks(userId!).then((r) => r.data),
    enabled: !!userId,
  });
  const propertiesQuery = useQuery({
    queryKey: ["resident-properties", userId],
    queryFn: () => propertiesApi.list().then((r) => r.data),
    enabled: !!userId,
  });

  const activeLinks = (linksQuery.data ?? []).filter((l) => l.is_active);
  const propertyById = new Map((propertiesQuery.data ?? []).map((p) => [p.id, p]));

  const options = activeLinks.map((link) => {
    const prop = propertyById.get(link.property_id);
    const label = prop
      ? `${prop.house_number}${prop.floor_number != null ? ` (Floor ${prop.floor_number})` : ""} — ${link.relationship_type === "OWNER" ? "Owner" : "Tenant"}`
      : `Property — ${link.relationship_type === "OWNER" ? "Owner" : "Tenant"}`;
    return { property_id: link.property_id, label };
  });

  useEffect(() => {
    if (activeLinks.length === 0 || !storageKey) return;
    const stillValid = activeLinks.some((l) => l.property_id === activePropertyId);
    if (!activePropertyId || !stillValid) {
      setActivePropertyIdState(activeLinks[0].property_id);
      localStorage.setItem(storageKey, activeLinks[0].property_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linksQuery.data, storageKey]);

  const setActivePropertyId = useCallback(
    (id: string) => {
      setActivePropertyIdState(id);
      if (storageKey) localStorage.setItem(storageKey, id);
    },
    [storageKey]
  );

  return {
    activePropertyId,
    setActivePropertyId,
    options,
    hasMultipleProperties: activeLinks.length > 1,
    isLoading: linksQuery.isLoading || propertiesQuery.isLoading,
    error: linksQuery.error ?? propertiesQuery.error,
  };
}
