import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "@/api/users";
import { residentsApi } from "@/api/residents";
import { propertiesApi, type PropertyOut, type PropertyResidentLink } from "@/api/properties";
import { Loader, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Modal } from "@/components/Modal";
import type { RelationshipType } from "@/types/enums";

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

      {profile.roles.includes("RESIDENT") && <MyPropertiesSection residentId={profile.id} />}
    </div>
  );
}

/**
 * Resident self-service property linking — "add" a property from the
 * Profile page instead of an Admin manually linking it. Unlike the
 * signup-time link (immediate) this goes to the Admin for approval first
 * (residentsApi.requestPropertyLink); shown for anyone who currently
 * holds a RESIDENT role, dual-role Admin+Resident included.
 */
function MyPropertiesSection({ residentId }: { residentId: string }) {
  const queryClient = useQueryClient();
  const [requesting, setRequesting] = useState(false);

  const linksQuery = useQuery({
    queryKey: ["profile", "my-properties", residentId],
    queryFn: () => propertiesApi.myLinks(residentId).then((r) => r.data),
  });
  const propertiesQuery = useQuery({
    queryKey: ["profile", "properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });
  const requestsQueryKey = ["profile", "property-link-requests"];
  const requestsQuery = useQuery({
    queryKey: requestsQueryKey,
    queryFn: () => residentsApi.myPropertyLinkRequests().then((r) => r.data),
  });

  const propertyById = new Map((propertiesQuery.data ?? []).map((p) => [p.id, p]));
  const activeLinks = (linksQuery.data ?? []).filter((l) => l.is_active);
  const pendingRequests = (requestsQuery.data ?? []).filter((r) => r.status === "PENDING");
  const pastRequests = (requestsQuery.data ?? []).filter((r) => r.status !== "PENDING");

  const requestableProperties = (propertiesQuery.data ?? []).filter(
    (p) =>
      !activeLinks.some((l) => l.property_id === p.id) &&
      !pendingRequests.some((r) => r.property_id === p.id)
  );

  return (
    <div className="space-y-4 rounded border border-line bg-paper p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-navy-muted">My properties</h2>
        <Button variant="secondary" onClick={() => setRequesting(true)}>+ Add property</Button>
      </div>

      {(linksQuery.isLoading || propertiesQuery.isLoading) && <Loader />}

      {!linksQuery.isLoading && activeLinks.length === 0 && (
        <p className="text-sm text-navy-muted">No properties linked yet.</p>
      )}
      {activeLinks.length > 0 && (
        <ul className="space-y-2">
          {activeLinks.map((l) => (
            <li key={l.id} className="border border-line rounded px-3 py-2 bg-white space-y-1.5">
              <div className="flex items-center justify-between text-sm text-ink">
                <span>{propertyById.get(l.property_id)?.house_number ?? "—"}</span>
                <span className="text-xs text-navy-muted">{l.relationship_type === "OWNER" ? "Owner" : "Tenant"}</span>
              </div>
              {l.relationship_type === "TENANT" && <OwnerContactRow link={l} residentId={residentId} />}
            </li>
          ))}
        </ul>
      )}

      {pendingRequests.length > 0 && (
        <div>
          <p className="text-xs text-navy-muted mb-1">Awaiting your Admin's approval</p>
          <ul className="space-y-1">
            {pendingRequests.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between text-sm text-ink border border-line rounded px-3 py-1.5 bg-white"
              >
                <span>
                  {propertyById.get(r.property_id)?.house_number ?? "—"}{" "}
                  <span className="text-xs text-navy-muted">
                    ({r.relationship_type === "OWNER" ? "Owner" : "Tenant"})
                  </span>
                </span>
                <Badge status="PENDING">Pending</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      {pastRequests.length > 0 && (
        <div>
          <p className="text-xs text-navy-muted mb-1">Past requests</p>
          <ul className="space-y-1">
            {pastRequests.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between text-sm text-ink border border-line rounded px-3 py-1.5 bg-white"
              >
                <span>{propertyById.get(r.property_id)?.house_number ?? "—"}</span>
                <Badge status={r.status}>{r.status === "APPROVED" ? "Approved" : "Rejected"}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      {requesting && (
        <RequestPropertyLinkModal
          properties={requestableProperties}
          onClose={() => setRequesting(false)}
          onSuccess={() => {
            setRequesting(false);
            void queryClient.invalidateQueries({ queryKey: requestsQueryKey });
          }}
        />
      )}
    </div>
  );
}

/**
 * Owner contact details for a Tenant's own link — a Tenant can now sign
 * up (or request a link) with no Owner account in the system at all, so
 * there's otherwise no record of who the Owner actually is. Self-filled,
 * free text, not a real account/login.
 */
function OwnerContactRow({ link, residentId }: { link: PropertyResidentLink; residentId: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(link.owner_contact_name ?? "");
  const [mobile, setMobile] = useState(link.owner_contact_mobile ?? "");

  const save = useMutation({
    mutationFn: () => residentsApi.updateOwnerContact(link.id, name.trim() || null, mobile.trim() || null),
    onSuccess: () => {
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["profile", "my-properties", residentId] });
    },
  });

  if (!editing) {
    return (
      <div className="flex items-center justify-between text-xs text-navy-muted pt-1 border-t border-line">
        {link.owner_contact_name || link.owner_contact_mobile ? (
          <span>
            Owner: {link.owner_contact_name || "—"}
            {link.owner_contact_mobile && ` · ${link.owner_contact_mobile}`}
          </span>
        ) : (
          <span>Owner details not added</span>
        )}
        <button className="underline shrink-0 ml-2" onClick={() => setEditing(true)}>
          {link.owner_contact_name || link.owner_contact_mobile ? "Edit" : "+ Add owner details"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2 pt-1 border-t border-line">
      <Input label="Owner's name" value={name} onChange={(e) => setName(e.target.value)} />
      <Input
        label="Owner's mobile (optional)"
        type="tel"
        inputMode="numeric"
        value={mobile}
        onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
      />
      {save.isError && (
        <p className="text-xs text-danger">{apiErrorMessage(save.error, "Couldn't save owner details.")}</p>
      )}
      <div className="flex justify-end gap-2">
        <button
          className="text-xs text-navy-muted underline"
          onClick={() => {
            setEditing(false);
            setName(link.owner_contact_name ?? "");
            setMobile(link.owner_contact_mobile ?? "");
          }}
        >
          Cancel
        </button>
        <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>
          Save
        </Button>
      </div>
    </div>
  );
}

function RequestPropertyLinkModal({
  properties, onClose, onSuccess,
}: { properties: PropertyOut[]; onClose: () => void; onSuccess: () => void }) {
  const [propertyId, setPropertyId] = useState("");
  const [relationshipType, setRelationshipType] = useState<RelationshipType>("OWNER");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: () => residentsApi.requestPropertyLink(propertyId, relationshipType, reason.trim() || undefined),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't submit the request.")),
  });

  return (
    <Modal open onClose={onClose} title="Add a property">
      <div className="space-y-4">
        <p className="text-xs text-navy-muted">
          This goes to your Admin for approval — it won't take effect until they approve it.
        </p>
        {properties.length === 0 ? (
          <p className="text-sm text-navy-muted">No other properties available to request right now.</p>
        ) : (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Property</label>
            <select
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            >
              <option value="">Select a property</option>
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.house_number} ({p.house_type === "FLAT" ? "Flat" : "Bungalow"})
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="block text-sm text-navy-muted mb-1">Relationship</label>
          <div className="flex gap-2">
            {(["OWNER", "TENANT"] as RelationshipType[]).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setRelationshipType(opt)}
                className={`px-3 py-1.5 rounded text-sm border ${
                  relationshipType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt === "OWNER" ? "Owner" : "Tenant"}
              </button>
            ))}
          </div>
        </div>
        <Input
          label="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. I bought this flat"
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={request.isPending} disabled={!propertyId} onClick={() => request.mutate()}>
            Submit
          </Button>
        </div>
      </div>
    </Modal>
  );
}
