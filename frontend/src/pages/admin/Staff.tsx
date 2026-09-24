import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffApi, type StaffOut } from "@/api/staff";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

/**
 * Manager and Security Guard are third-party hired staff, not Residents —
 * unlike Admin/Resident signup there's no property link and no approval
 * wait: the Admin creating the account here IS the approval, same as
 * Sub-admin promotion is unilateral (see AssignSubAdmin.tsx, the closest
 * existing pattern this mirrors).
 */
export function AdminStaff() {
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [role, setRole] = useState<"MANAGER" | "SECURITY_GUARD">("MANAGER");
  const [error, setError] = useState<string | null>(null);

  const staffQueryKey = ["admin", "staff"];
  const staffQuery = useQuery({
    queryKey: staffQueryKey,
    queryFn: () => staffApi.list().then((r) => r.data),
  });

  const create = useMutation({
    mutationFn: () => staffApi.create({ full_name: fullName.trim(), mobile: mobile.trim(), role }),
    onSuccess: () => {
      setFullName("");
      setMobile("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: staffQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Could not create this account.")),
  });

  const remove = useMutation({
    mutationFn: (userId: string) => staffApi.remove(userId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: staffQueryKey }),
  });

  function handleRemove(s: StaffOut) {
    if (window.confirm(`Remove ${s.full_name} as ${s.role === "MANAGER" ? "Manager" : "Security Guard"}?`)) {
      remove.mutate(s.id);
    }
  }

  const mobileValid = /^\d{10}$/.test(mobile.trim());

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Staff</h1>

      <div className="space-y-4 rounded border border-line bg-paper p-4 max-w-md">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Role</label>
          <select
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            value={role}
            onChange={(e) => setRole(e.target.value as "MANAGER" | "SECURITY_GUARD")}
          >
            <option value="MANAGER">Manager</option>
            <option value="SECURITY_GUARD">Security Guard</option>
          </select>
        </div>
        <Input label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <Input
          label="Mobile number"
          value={mobile}
          onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
          error={mobile && !mobileValid ? "Enter a valid 10-digit mobile number" : undefined}
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end">
          <Button
            loading={create.isPending}
            disabled={!fullName.trim() || !mobileValid}
            onClick={() => create.mutate()}
          >
            Add
          </Button>
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Current staff</h2>
        {staffQuery.isLoading && <Loader />}
        {staffQuery.isError && (
          <ErrorState message="Couldn't load staff." onRetry={() => staffQuery.refetch()} />
        )}
        {staffQuery.data && staffQuery.data.length === 0 && (
          <EmptyState title="No Manager or Security Guard accounts yet" />
        )}
        {staffQuery.data && staffQuery.data.length > 0 && (
          <Table<StaffOut>
            keyFor={(s) => s.id}
            columns={[
              { header: "Name", render: (s) => s.full_name },
              { header: "Mobile", render: (s) => s.mobile },
              { header: "Role", render: (s) => <Badge status={s.role}>{s.role === "MANAGER" ? "Manager" : "Security Guard"}</Badge> },
              {
                header: "",
                render: (s) => (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => handleRemove(s)}
                      disabled={remove.isPending}
                      className="text-xs text-danger underline"
                    >
                      Remove
                    </button>
                  </div>
                ),
              },
            ]}
            rows={staffQuery.data}
          />
        )}
      </section>
    </div>
  );
}
