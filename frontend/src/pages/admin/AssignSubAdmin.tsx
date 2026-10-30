import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { residentsApi, subadminsApi, type ResidentOut, type SubAdminAssignmentOut } from "@/api/residents";
import { locationsApi, type SocietyLocationOut } from "@/api/societies";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";

/**
 * A Wing/Row-first way to assign a Sub-admin — pick one or more Wings/
 * Rows first (a single Sub-admin can cover several — Section 7's only
 * cardinality rule is one active Sub-admin per Wing/Row, not the
 * reverse), then one of the residents actually living in any of them,
 * instead of the old per-resident "Sub-admin" button that showed on
 * every row in the Residents table regardless of whether it made sense
 * there. Works the same for a Flats (Wing) or Bungalow (Row) society —
 * list_residents_by_location doesn't care which.
 */
export function AssignSubAdmin() {
  const queryClient = useQueryClient();
  const [locationIds, setLocationIds] = useState<string[]>([]);
  const [residentId, setResidentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: ["admin", "locations"],
    queryFn: () => locationsApi.list().then((r) => r.data),
  });

  const assignmentsQueryKey = ["admin", "subadmins", "all"];
  const assignmentsQuery = useQuery({
    queryKey: assignmentsQueryKey,
    queryFn: () => subadminsApi.listAll().then((r) => r.data),
  });

  // Union of residents across every selected Wing/Row, deduped — a
  // resident living in any one of them is a reasonable pick to
  // administer the combined scope.
  const residentsQuery = useQuery({
    queryKey: ["admin", "residents", "by-location", [...locationIds].sort().join(",")],
    queryFn: async () => {
      const lists = await Promise.all(locationIds.map((id) => residentsApi.byLocation(id).then((r) => r.data)));
      const byId = new Map<string, ResidentOut>();
      for (const list of lists) {
        for (const r of list) byId.set(r.id, r);
      }
      return [...byId.values()].sort((a, b) => a.full_name.localeCompare(b.full_name));
    },
    enabled: locationIds.length > 0,
  });

  const assign = useMutation({
    mutationFn: () => subadminsApi.promote(residentId, locationIds),
    onSuccess: () => {
      const resident = (residentsQuery.data ?? []).find((r) => r.id === residentId);
      const names = locations.filter((l) => locationIds.includes(l.id)).map(locationLabel).join(", ");
      setSuccess(`${resident?.full_name ?? "Resident"} is now Sub-admin of ${names}.`);
      setError(null);
      setResidentId("");
      void queryClient.invalidateQueries({ queryKey: assignmentsQueryKey });
    },
    onError: (e) => {
      setError(apiErrorMessage(e, "Could not assign Sub-admin."));
      setSuccess(null);
    },
  });

  const revoke = useMutation({
    mutationFn: (scopeId: string) => subadminsApi.revokeScope(scopeId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: assignmentsQueryKey }),
  });

  function handleRevoke(a: SubAdminAssignmentOut) {
    if (window.confirm(`Remove ${a.sub_admin_name} as Sub-admin of ${a.location_name}?`)) {
      revoke.mutate(a.scope_id);
    }
  }

  function locationLabel(l: SocietyLocationOut | undefined): string {
    if (!l) return "—";
    return `${l.name} (${l.location_type === "WING" ? "Wing" : "Row"})`;
  }

  const locations = locationsQuery.data ?? [];
  const sortedLocations = [...locations].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" })
  );
  const assignedLocationIds = new Set((assignmentsQuery.data ?? []).map((a) => a.location_id));

  function toggleLocation(id: string, checked: boolean) {
    setLocationIds((prev) => (checked ? [...prev, id] : prev.filter((existing) => existing !== id)));
    setResidentId("");
    setError(null);
    setSuccess(null);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Assign Sub-admin</h1>

      <div className="space-y-4 rounded border border-line bg-paper p-4 max-w-md">
        <div>
          <label className="block text-sm text-navy-muted mb-1">
            Wing / Row <span className="text-xs text-navy-muted">(pick one or more — one Sub-admin can cover several)</span>
          </label>
          {locationsQuery.isLoading && <Loader />}
          {locationsQuery.isError && (
            <ErrorState message="Couldn't load Wings/Rows." onRetry={() => locationsQuery.refetch()} />
          )}
          {locations.length === 0 && !locationsQuery.isLoading && !locationsQuery.isError && (
            <p className="text-xs text-navy-muted">No Wings/Rows on record yet — add them from the Properties page.</p>
          )}
          {locations.length > 0 && (
            <div className="space-y-1 max-h-56 overflow-y-auto border border-line rounded p-2">
              {sortedLocations.map((l) => {
                const alreadyAssigned = assignedLocationIds.has(l.id);
                return (
                  <label
                    key={l.id}
                    className={`flex items-center gap-2 text-sm px-1 py-0.5 ${alreadyAssigned ? "text-navy-muted/60" : "text-ink"}`}
                  >
                    <input
                      type="checkbox"
                      checked={locationIds.includes(l.id)}
                      disabled={alreadyAssigned}
                      onChange={(e) => toggleLocation(l.id, e.target.checked)}
                    />
                    {locationLabel(l)}
                    {alreadyAssigned && <span className="text-xs"> — already has a Sub-admin</span>}
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {locationIds.length > 0 && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Resident</label>
            {residentsQuery.isLoading && <Loader />}
            {residentsQuery.isError && (
              <ErrorState message="Couldn't load residents." onRetry={() => residentsQuery.refetch()} />
            )}
            {residentsQuery.data && residentsQuery.data.length === 0 && (
              <p className="text-xs text-navy-muted">No residents are linked to a property in this Wing/Row yet.</p>
            )}
            {residentsQuery.data && residentsQuery.data.length > 0 && (
              <div className="space-y-1 max-h-56 overflow-y-auto border border-line rounded p-2">
                {residentsQuery.data.map((r: ResidentOut) => (
                  <label key={r.id} className="flex items-center gap-2 text-sm text-ink px-1 py-0.5">
                    <input
                      type="radio"
                      name="resident"
                      checked={residentId === r.id}
                      onChange={() => setResidentId(r.id)}
                    />
                    {r.full_name} <span className="text-xs text-navy-muted">({r.mobile})</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}
        {success && !assign.isPending && <p className="text-sm text-success">{success}</p>}

        <div className="flex justify-end">
          <Button loading={assign.isPending} disabled={!residentId} onClick={() => assign.mutate()}>
            Assign
          </Button>
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Current Sub-admins</h2>
        {assignmentsQuery.isLoading && <Loader />}
        {assignmentsQuery.isError && (
          <ErrorState message="Couldn't load Sub-admins." onRetry={() => assignmentsQuery.refetch()} />
        )}
        {assignmentsQuery.data && assignmentsQuery.data.length === 0 && (
          <EmptyState title="No Sub-admins assigned yet" />
        )}
        {assignmentsQuery.data && assignmentsQuery.data.length > 0 && (
          <Table<SubAdminAssignmentOut>
            keyFor={(a) => a.scope_id}
            columns={[
              { header: "Wing / Row", render: (a) => `${a.location_name} (${a.location_type === "WING" ? "Wing" : "Row"})` },
              { header: "Sub-admin", render: (a) => a.sub_admin_name },
              { header: "Mobile", render: (a) => a.sub_admin_mobile },
              {
                header: "",
                render: (a) => (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => handleRevoke(a)}
                      disabled={revoke.isPending}
                      className="text-xs text-danger underline"
                    >
                      Remove
                    </button>
                  </div>
                ),
              },
            ]}
            rows={assignmentsQuery.data}
          />
        )}
      </section>
    </div>
  );
}
