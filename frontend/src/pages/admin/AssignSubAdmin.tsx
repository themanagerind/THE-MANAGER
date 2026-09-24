import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { residentsApi, subadminsApi, type ResidentOut, type SubAdminAssignmentOut } from "@/api/residents";
import { locationsApi, type SocietyLocationOut } from "@/api/societies";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";

/**
 * A Wing/Row-first way to assign a Sub-admin — pick the Wing/Row first,
 * then one of the residents actually living there, instead of the old
 * per-resident "Sub-admin" button that showed on every row in the
 * Residents table regardless of whether it made sense there. Works the
 * same for a Flats (Wing) or Bungalow (Row) society — list_residents_by_
 * location doesn't care which.
 */
export function AssignSubAdmin() {
  const queryClient = useQueryClient();
  const [locationId, setLocationId] = useState("");
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

  const residentsQuery = useQuery({
    queryKey: ["admin", "residents", "by-location", locationId],
    queryFn: () => residentsApi.byLocation(locationId).then((r) => r.data),
    enabled: !!locationId,
  });

  const assign = useMutation({
    mutationFn: () => subadminsApi.promote(residentId, [locationId]),
    onSuccess: () => {
      const resident = (residentsQuery.data ?? []).find((r) => r.id === residentId);
      setSuccess(`${resident?.full_name ?? "Resident"} is now Sub-admin of ${locationLabel(selectedLocation)}.`);
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
  const selectedLocation = locations.find((l) => l.id === locationId);
  const assignedLocationIds = new Set((assignmentsQuery.data ?? []).map((a) => a.location_id));

  function handleLocationChange(id: string) {
    setLocationId(id);
    setResidentId("");
    setError(null);
    setSuccess(null);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Assign Sub-admin</h1>

      <div className="space-y-4 rounded border border-line bg-paper p-4 max-w-md">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Wing / Row</label>
          {locationsQuery.isLoading && <Loader />}
          {locationsQuery.isError && (
            <ErrorState message="Couldn't load Wings/Rows." onRetry={() => locationsQuery.refetch()} />
          )}
          {locations.length === 0 && !locationsQuery.isLoading && !locationsQuery.isError && (
            <p className="text-xs text-navy-muted">No Wings/Rows on record yet — add them from the Properties page.</p>
          )}
          {locations.length > 0 && (
            <select
              className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
              value={locationId}
              onChange={(e) => handleLocationChange(e.target.value)}
            >
              <option value="">Select a Wing/Row</option>
              {sortedLocations.map((l) => (
                <option key={l.id} value={l.id}>
                  {locationLabel(l)}
                  {assignedLocationIds.has(l.id) ? " — already has a Sub-admin" : ""}
                </option>
              ))}
            </select>
          )}
        </div>

        {locationId && (
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
