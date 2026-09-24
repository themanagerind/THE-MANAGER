import { apiClient } from "@/api/client";
import type { LocationType, RelationshipType, Role, RoleRequestStatus, UserStatus } from "@/types/enums";

export interface ResidentOut {
  id: string;
  society_id: string | null;
  full_name: string;
  mobile: string;
  email: string | null;
  status: UserStatus;
  created_at: string;
}

export interface PropertyResidentOut {
  id: string;
  property_id: string;
  resident_id: string;
  relationship_type: RelationshipType;
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
  owner_contact_name: string | null;
  owner_contact_mobile: string | null;
}

export interface SubAdminScopeOut {
  id: string;
  sub_admin_id: string;
  location_id: string;
  assigned_by: string;
  assigned_at: string;
  revoked_at: string | null;
}

export interface SubAdminAssignmentOut {
  scope_id: string;
  sub_admin_id: string;
  sub_admin_name: string;
  sub_admin_mobile: string;
  location_id: string;
  location_name: string;
  location_type: LocationType;
  assigned_at: string;
}

export interface RoleRequestOut {
  id: string;
  user_id: string;
  society_id: string;
  status: RoleRequestStatus;
  reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  decision_reason: string | null;
  created_at: string;
}

export interface PropertyLinkRequestOut {
  id: string;
  society_id: string;
  resident_id: string;
  property_id: string;
  relationship_type: RelationshipType;
  status: RoleRequestStatus;
  reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  decision_reason: string | null;
  created_at: string;
}

export const residentsApi = {
  /** Public — no auth required. Resident waits for their society's Admin
   * to approve (see pending/decideApproval below). property_id/
   * relationship_type are required — the Resident picks their own house
   * (from societiesApi.publicProperties) and Owner/Tenant right at
   * signup, same for a Flats or Bungalow society; the link exists
   * immediately but stays inert until Admin approval. */
  signup: (input: {
    full_name: string; mobile: string; email?: string; society_id: string;
    property_id: string; relationship_type: RelationshipType;
  }) => apiClient.post<ResidentOut>("/residents/signup", input),
  /** Admin's resident directory — e.g. the "Make Sub-admin" picker
   * (status="ACTIVE"), separate from pending() below which is
   * specifically the approval queue. Omit status for every resident
   * regardless of approval state. */
  list: (status?: UserStatus) => apiClient.get<ResidentOut[]>("/residents", { params: { status } }),
  pending: () => apiClient.get<ResidentOut[]>("/residents/pending"),
  decideApproval: (id: string, approve: boolean, rejectionReason?: string) =>
    apiClient.post<ResidentOut>(`/residents/${id}/approval`, { approve, rejection_reason: rejectionReason }),
  linkProperty: (propertyId: string, residentId: string, relationshipType: RelationshipType) =>
    apiClient.post<PropertyResidentOut>("/residents/property-links", {
      property_id: propertyId, resident_id: residentId, relationship_type: relationshipType,
    }),
  unlinkProperty: (linkId: string) => apiClient.delete<PropertyResidentOut>(`/residents/property-links/${linkId}`),
  /** Admin-only — links the CALLER (not another user) to a property in
   * their own society, granting a RESIDENT role on their existing account
   * if they don't already have one (Section 4 dual-role: ADMIN+RESIDENT).
   * No approval step — the caller already runs the society. */
  linkSelf: (propertyId: string, relationshipType: RelationshipType) =>
    apiClient.post<PropertyResidentOut>("/residents/self-link", {
      property_id: propertyId, relationship_type: relationshipType,
    }),
  byProperty: (propertyId: string) => apiClient.get<PropertyResidentOut[]>(`/residents/by-property/${propertyId}`),
  /** Powers the Assign Sub-admin page's picker — Admin picks a Wing/Row
   * first, then one of the residents actually living there. */
  byLocation: (locationId: string) => apiClient.get<ResidentOut[]>(`/residents/by-location/${locationId}`),
  /** Tenant-only, on their own active link — self-recording the Owner's
   * contact details (free text, not a real account) since a Tenant can
   * now sign up with no Owner account in the system to look this up
   * from. Pass null/omit to clear a field. */
  updateOwnerContact: (linkId: string, ownerContactName?: string | null, ownerContactMobile?: string | null) =>
    apiClient.patch<PropertyResidentOut>(`/residents/property-links/${linkId}/owner-contact`, {
      owner_contact_name: ownerContactName, owner_contact_mobile: ownerContactMobile,
    }),
  /** Resident-only — from their own Profile page, requesting to link
   * themselves to an additional property. Unlike linkSelf/signup, this
   * stays PENDING until the Admin approves it (see decidePropertyLinkRequest
   * below) — approval is what actually creates the real link. */
  requestPropertyLink: (propertyId: string, relationshipType: RelationshipType, reason?: string) =>
    apiClient.post<PropertyLinkRequestOut>("/residents/property-link-requests", {
      property_id: propertyId, relationship_type: relationshipType, reason,
    }),
  /** Resident's own requests, any status — so their Profile page can show
   * pending/approved/rejected instead of the request just vanishing. */
  myPropertyLinkRequests: () => apiClient.get<PropertyLinkRequestOut[]>("/residents/property-link-requests/mine"),
  pendingPropertyLinkRequests: () =>
    apiClient.get<PropertyLinkRequestOut[]>("/residents/property-link-requests/pending"),
  decidePropertyLinkRequest: (requestId: string, approve: boolean, decisionReason?: string) =>
    apiClient.post<PropertyLinkRequestOut>(`/residents/property-link-requests/${requestId}/decision`, {
      approve, decision_reason: decisionReason,
    }),
};

export const subadminsApi = {
  /** Every active Sub-admin scope in the society, denormalized with
   * names — the Assign Sub-admin page's "Current Sub-admins" overview. */
  listAll: () => apiClient.get<SubAdminAssignmentOut[]>("/subadmins"),
  promote: (residentId: string, locationIds: string[]) =>
    apiClient.post<SubAdminScopeOut[]>("/subadmins/promote", { resident_id: residentId, location_ids: locationIds }),
  scopes: (subAdminId: string) => apiClient.get<SubAdminScopeOut[]>(`/subadmins/${subAdminId}/scopes`),
  assignScope: (subAdminId: string, locationId: string) =>
    apiClient.post<SubAdminScopeOut>(`/subadmins/${subAdminId}/scopes`, { location_id: locationId }),
  revokeScope: (scopeId: string) => apiClient.delete<SubAdminScopeOut>(`/subadmins/scopes/${scopeId}`),
  /** Admin directly removes someone's Sub-admin role and every active
   * scope, in one shot — no resignation request needed. */
  demote: (subAdminId: string) => apiClient.delete(`/subadmins/${subAdminId}`),
  submitResignation: (reason?: string) => apiClient.post<RoleRequestOut>("/subadmins/resignation", { reason }),
  pendingResignations: () => apiClient.get<RoleRequestOut[]>("/subadmins/resignations/pending"),
  decideResignation: (requestId: string, approve: boolean, decisionReason?: string) =>
    apiClient.post<RoleRequestOut>(`/subadmins/resignations/${requestId}/decision`, { approve, decision_reason: decisionReason }),
};

export type { Role };
