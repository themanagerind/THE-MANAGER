import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  adminChangeApi, type AdminChangeRequestOut, type ResignationCandidateOut, type RoleHistoryOut,
} from "@/api/adminChange";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

/**
 * An Admin resigns and picks their own successor — an existing Resident
 * or Sub-admin in their society, same unanimous-Sub-admin-approval rule
 * as the Platform Owner's "Change Admin" flow (see
 * admin_change_service.create_resignation_request). Also shows this
 * society's full Admin/Sub-admin work-period history — user_roles.
 * assigned_at/revoked_at already IS that history, this just surfaces it.
 */
export function AdminResign() {
  const [candidateId, setCandidateId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AdminChangeRequestOut | null>(null);

  const candidatesQuery = useQuery({
    queryKey: ["admin", "resignation-candidates"],
    queryFn: () => adminChangeApi.resignationCandidates().then((r) => r.data),
  });
  const historyQuery = useQuery({
    queryKey: ["admin", "role-history"],
    queryFn: () => adminChangeApi.history().then((r) => r.data),
  });

  const resign = useMutation({
    mutationFn: () => adminChangeApi.resign(candidateId),
    onSuccess: (r) => {
      setResult(r.data);
      setError(null);
    },
    onError: (e) => {
      setError(apiErrorMessage(e, "Could not submit your resignation."));
      setResult(null);
    },
  });

  const candidates = candidatesQuery.data ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Resign as Admin</h1>

      <div className="space-y-4 rounded border border-line bg-paper p-4 max-w-md">
        <p className="text-sm text-navy-muted">
          Pick your successor from an existing Resident or Sub-admin in this society. Once you proceed, every
          Sub-admin must approve before the handover actually happens — a single reject cancels it.
        </p>

        {candidatesQuery.isLoading && <Loader />}
        {candidatesQuery.isError && (
          <ErrorState message="Couldn't load candidates." onRetry={() => candidatesQuery.refetch()} />
        )}
        {!candidatesQuery.isLoading && candidates.length === 0 && (
          <p className="text-xs text-navy-muted">No Residents or Sub-admins on record yet to hand over to.</p>
        )}
        {candidates.length > 0 && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Successor</label>
            <select
              className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
              value={candidateId}
              onChange={(e) => { setCandidateId(e.target.value); setResult(null); setError(null); }}
            >
              <option value="">Select a Resident or Sub-admin</option>
              {candidates.map((c: ResignationCandidateOut) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} ({c.mobile}) — {c.role_label === "SUB_ADMIN" ? "Sub-admin" : "Resident"}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}
        {result && !resign.isPending && (
          <p className="text-sm text-success">
            {result.status === "APPROVED"
              ? `Done — ${result.new_admin_full_name} is now the Admin (no Sub-admins to approve).`
              : `Sent — waiting on ${result.approvals_total} Sub-admin${result.approvals_total !== 1 ? "s" : ""} to approve.`}
          </p>
        )}

        <div className="flex justify-end">
          <Button variant="danger" loading={resign.isPending} disabled={!candidateId} onClick={() => resign.mutate()}>
            Proceed
          </Button>
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Admin &amp; Sub-admin work history</h2>
        {historyQuery.isLoading && <Loader />}
        {historyQuery.isError && (
          <ErrorState message="Couldn't load history." onRetry={() => historyQuery.refetch()} />
        )}
        {historyQuery.data && historyQuery.data.length === 0 && <EmptyState title="No history yet" />}
        {historyQuery.data && historyQuery.data.length > 0 && (
          <Table<RoleHistoryOut>
            keyFor={(r) => r.id}
            columns={[
              { header: "Name", render: (r) => r.full_name },
              { header: "Role", render: (r) => (r.role === "ADMIN" ? "Admin" : "Sub-admin") },
              { header: "From", render: (r) => formatDateTime(r.assigned_at) },
              { header: "To", render: (r) => (r.revoked_at ? formatDateTime(r.revoked_at) : "Current") },
            ]}
            rows={historyQuery.data}
          />
        )}
      </section>
    </div>
  );
}
