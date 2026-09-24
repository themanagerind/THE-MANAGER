import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adminChangeApi, type AdminChangeRequestOut, type ResignationCandidateOut, type RoleHistoryOut,
} from "@/api/adminChange";
import { societiesApi, type SocietyLocationOut } from "@/api/societies";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

/**
 * Platform Owner replaces a society's Admin — at most one active Admin
 * per society (Section: one-Admin invariant), so "change" always means
 * "replace the current one", not "add another". Finalizes immediately if
 * the society has no Sub-admin to weigh in; otherwise every Sub-admin in
 * that society must approve (unanimous — a single reject cancels the
 * whole request) before the swap actually happens. See
 * admin_change_service.py for the full flow.
 */
export function ChangeAdmin() {
  const queryClient = useQueryClient();
  const [societyId, setSocietyId] = useState("");
  const [mode, setMode] = useState<"pick" | "manual">("pick");
  const [locationId, setLocationId] = useState("");
  const [search, setSearch] = useState("");
  const [newAdminUserId, setNewAdminUserId] = useState("");
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AdminChangeRequestOut | null>(null);

  const societiesQuery = useQuery({
    queryKey: ["platform", "societies"],
    queryFn: () => societiesApi.list().then((r) => r.data),
  });
  const requestsQueryKey = ["platform", "admin-change-requests"];
  const requestsQuery = useQuery({
    queryKey: requestsQueryKey,
    queryFn: () => adminChangeApi.list().then((r) => r.data),
  });
  const historyQuery = useQuery({
    queryKey: ["platform", "role-history", societyId],
    queryFn: () => adminChangeApi.history(societyId).then((r) => r.data),
    enabled: !!societyId,
  });
  const locationsQuery = useQuery({
    queryKey: ["platform", "locations", societyId],
    queryFn: () => societiesApi.listLocations(societyId).then((r) => r.data),
    enabled: !!societyId && mode === "pick",
  });
  const candidatesQuery = useQuery({
    queryKey: ["platform", "admin-change-candidates", societyId, locationId],
    queryFn: () => adminChangeApi.candidates(societyId, locationId || undefined).then((r) => r.data),
    enabled: !!societyId && mode === "pick",
  });

  function resetForm() {
    setMode("pick");
    setLocationId("");
    setSearch("");
    setNewAdminUserId("");
    setFullName("");
    setMobile("");
    setEmail("");
  }

  const create = useMutation({
    mutationFn: () =>
      adminChangeApi.create(
        societyId,
        mode === "pick"
          ? { newAdminUserId }
          : { fullName: fullName.trim(), mobile, email: email.trim() || undefined }
      ),
    onSuccess: (r) => {
      setResult(r.data);
      setError(null);
      resetForm();
      void queryClient.invalidateQueries({ queryKey: requestsQueryKey });
    },
    onError: (e) => {
      setError(apiErrorMessage(e, "Could not create the Admin-change request."));
      setResult(null);
    },
  });

  const activeSocieties = (societiesQuery.data ?? []).filter((s) => s.status === "ACTIVE");
  const societyById = new Map((societiesQuery.data ?? []).map((s) => [s.id, s]));

  function locationLabel(l: SocietyLocationOut | undefined): string {
    if (!l) return "—";
    return `${l.name} (${l.location_type === "WING" ? "Wing" : "Row"})`;
  }

  function candidateLabel(c: ResignationCandidateOut): string {
    const parts: string[] = [];
    if (c.house_number) parts.push(c.house_number);
    if (c.floor_number != null) parts.push(`Floor ${c.floor_number}`);
    if (c.location_name) parts.push(c.location_name);
    return parts.length > 0 ? parts.join(" · ") : "No property linked";
  }

  const searchLower = search.trim().toLowerCase();
  const filteredCandidates = (candidatesQuery.data ?? []).filter((c) => {
    if (!searchLower) return true;
    return (
      c.full_name.toLowerCase().includes(searchLower) ||
      c.mobile.includes(searchLower) ||
      (c.house_number ?? "").toLowerCase().includes(searchLower) ||
      (c.location_name ?? "").toLowerCase().includes(searchLower)
    );
  });

  const canSubmit =
    societyId.length > 0 &&
    (mode === "pick" ? newAdminUserId.length > 0 : fullName.trim().length > 0 && /^\d{10}$/.test(mobile));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Change Admin</h1>

      <div className="space-y-4 rounded border border-line bg-paper p-4 max-w-md">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Society</label>
          {societiesQuery.isLoading && <Loader />}
          {societiesQuery.isError && (
            <ErrorState message="Couldn't load societies." onRetry={() => societiesQuery.refetch()} />
          )}
          {activeSocieties.length > 0 && (
            <select
              className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
              value={societyId}
              onChange={(e) => { setSocietyId(e.target.value); resetForm(); setResult(null); setError(null); }}
            >
              <option value="">Select a society</option>
              {activeSocieties.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
        </div>

        {societyId && (
          <>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode("pick")}
                className={`px-3 py-1.5 rounded text-sm border ${
                  mode === "pick" ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                Pick existing Resident/Sub-admin
              </button>
              <button
                type="button"
                onClick={() => setMode("manual")}
                className={`px-3 py-1.5 rounded text-sm border ${
                  mode === "manual" ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                Enter a new person manually
              </button>
            </div>

            {mode === "pick" ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-navy-muted mb-1">Wing / Row</label>
                  {locationsQuery.isLoading && <Loader />}
                  {locationsQuery.isError && (
                    <ErrorState message="Couldn't load Wings/Rows." onRetry={() => locationsQuery.refetch()} />
                  )}
                  <select
                    className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
                    value={locationId}
                    onChange={(e) => { setLocationId(e.target.value); setNewAdminUserId(""); }}
                  >
                    <option value="">All Wings/Rows</option>
                    {(locationsQuery.data ?? []).map((l) => (
                      <option key={l.id} value={l.id}>{locationLabel(l)}</option>
                    ))}
                  </select>
                </div>

                <Input
                  label="Search by name, mobile, or flat/house number"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="e.g. Sharma, 98765..., or 12-A"
                />

                {candidatesQuery.isLoading && <Loader />}
                {candidatesQuery.isError && (
                  <ErrorState message="Couldn't load candidates." onRetry={() => candidatesQuery.refetch()} />
                )}
                {candidatesQuery.data && candidatesQuery.data.length === 0 && (
                  <p className="text-xs text-navy-muted">
                    No active Residents or Sub-admins in this society yet.
                  </p>
                )}
                {candidatesQuery.data && candidatesQuery.data.length > 0 && filteredCandidates.length === 0 && (
                  <p className="text-xs text-navy-muted">No match for "{search}".</p>
                )}
                {filteredCandidates.length > 0 && (
                  <div className="space-y-1 max-h-64 overflow-y-auto border border-line rounded p-2">
                    {filteredCandidates.map((c) => (
                      <label key={c.id} className="flex items-center gap-2 text-sm text-ink px-1 py-1">
                        <input
                          type="radio"
                          name="candidate"
                          checked={newAdminUserId === c.id}
                          onChange={() => setNewAdminUserId(c.id)}
                        />
                        <span className="flex-1">
                          {c.full_name} <span className="text-xs text-navy-muted">({c.mobile})</span>
                        </span>
                        <Badge>{c.role_label === "SUB_ADMIN" ? "Sub-admin" : "Resident"}</Badge>
                        <span className="text-xs text-navy-muted shrink-0">{candidateLabel(c)}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <>
                <Input label="New Admin's full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
                <Input
                  label="New Admin's mobile number"
                  type="tel"
                  inputMode="numeric"
                  placeholder="10-digit mobile number"
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
                />
                <Input
                  label="New Admin's email (optional)"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </>
            )}
          </>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}
        {result && !create.isPending && (
          <p className="text-sm text-success">
            {result.status === "APPROVED"
              ? `Done — ${result.new_admin_full_name} is now the Admin (no Sub-admins to approve).`
              : `Request sent — waiting on ${result.approvals_total} Sub-admin${result.approvals_total !== 1 ? "s" : ""} to approve.`}
          </p>
        )}

        <div className="flex justify-end">
          <Button loading={create.isPending} disabled={!canSubmit} onClick={() => create.mutate()}>
            Proceed
          </Button>
        </div>
      </div>

      {societyId && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-navy-muted">
            Admin &amp; Sub-admin work history — {societyById.get(societyId)?.name ?? "this society"}
          </h2>
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
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Recent Admin-change requests</h2>
        {requestsQuery.isLoading && <Loader />}
        {requestsQuery.isError && (
          <ErrorState message="Couldn't load requests." onRetry={() => requestsQuery.refetch()} />
        )}
        {requestsQuery.data && requestsQuery.data.length === 0 && (
          <EmptyState title="No Admin-change requests yet" />
        )}
        {requestsQuery.data && requestsQuery.data.length > 0 && (
          <Table<AdminChangeRequestOut>
            keyFor={(r) => r.id}
            columns={[
              { header: "Society", render: (r) => societyById.get(r.society_id)?.name ?? "—" },
              { header: "New Admin", render: (r) => `${r.new_admin_full_name} (${r.new_admin_mobile})` },
              {
                header: "Progress",
                render: (r) => (r.approvals_total === 0 ? "No Sub-admins" : `${r.approvals_done} / ${r.approvals_total} approved`),
              },
              { header: "Status", render: (r) => <Badge status={r.status}>{r.status}</Badge> },
            ]}
            rows={requestsQuery.data}
          />
        )}
      </section>
    </div>
  );
}
