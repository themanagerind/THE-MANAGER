import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "@/api/users";
import { Loader, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

const roleLabels: Record<string, string> = {
  PLATFORM_OWNER: "Platform Owner",
  ADMIN: "Admin",
  SUB_ADMIN: "Sub-admin",
  MANAGER: "Manager",
  RESIDENT: "Resident",
  SECURITY_GUARD: "Security Guard",
};

/**
 * Self-service profile — same page for every role (Admin, Resident, ...):
 * name/email are editable, mobile is shown but not editable here (it's
 * the OTP login identity and is uniqueness-constrained, so changing it
 * needs its own re-verification flow, not a plain profile edit).
 */
export function Profile() {
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [success, setSuccess] = useState(false);

  const profileQuery = useQuery({
    queryKey: ["profile", "me"],
    queryFn: () => usersApi.me().then((r) => r.data),
  });

  useEffect(() => {
    if (profileQuery.data) {
      setFullName(profileQuery.data.full_name);
      setEmail(profileQuery.data.email ?? "");
    }
  }, [profileQuery.data]);

  const update = useMutation({
    mutationFn: () => usersApi.updateProfile(fullName.trim(), email.trim() || undefined),
    onSuccess: () => {
      setSuccess(true);
      void queryClient.invalidateQueries({ queryKey: ["profile", "me"] });
    },
    onError: () => setSuccess(false),
  });

  if (profileQuery.isLoading) return <Loader />;
  if (profileQuery.isError) {
    return <ErrorState message="Couldn't load your profile." onRetry={() => profileQuery.refetch()} />;
  }
  const profile = profileQuery.data!;

  const dirty = fullName.trim() !== profile.full_name || email.trim() !== (profile.email ?? "");

  return (
    <div className="space-y-6 max-w-md">
      <h1 className="text-xl font-semibold text-navy">My Profile</h1>

      <div className="flex flex-wrap gap-1.5">
        {profile.roles.map((r) => (
          <Badge key={r}>{roleLabels[r] ?? r}</Badge>
        ))}
      </div>

      <div className="space-y-4 rounded border border-line bg-paper p-4">
        <Input
          label="Full name"
          value={fullName}
          onChange={(e) => { setFullName(e.target.value); setSuccess(false); }}
        />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Mobile number</label>
          <p className="px-3 py-2 border border-line rounded text-sm text-navy-muted bg-white">
            {profile.mobile}
          </p>
          <p className="text-xs text-navy-muted mt-1">
            Not editable here — this is your login number. Contact your Admin if it needs to change.
          </p>
        </div>
        <Input
          label="Email (optional)"
          type="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setSuccess(false); }}
        />

        {update.isError && (
          <p className="text-sm text-danger">{apiErrorMessage(update.error, "Couldn't save your profile.")}</p>
        )}
        {success && !update.isPending && <p className="text-sm text-success">Saved.</p>}

        <div className="flex justify-end">
          <Button loading={update.isPending} disabled={!dirty || !fullName.trim()} onClick={() => update.mutate()}>
            Save changes
          </Button>
        </div>
      </div>
    </div>
  );
}
