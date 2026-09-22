import { apiClient } from "@/api/client";
import type { RelationshipType, Role, RoleRequestStatus, UserStatus } from "@/types/enums";

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
}

export interface SubAdminScopeOut {
  id: string;
  sub_admin_id: string;
  location_id: string;
  assigned_by: string;
  assigned_at: string;
  revoked_at: string | null;
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

export const residentsApi = {
  /** Public — no auth required. Resident waits for their society's Admin
   * to approve (see pending/decideApproval below). */
  signup: (input: { full_name: string; mobile: string; email?: string; society_id: string }) =>
    apiClient.post<ResidentOut>("/residents/signup", input),
  pending: () => apiClient.get<ResidentOut[]>("/residents/pending"),
  decideApproval: (id: string, approve: boolean, rejectionReason?: string) =>
    apiClient.post<ResidentOut>(`/residents/${id}/approval`, { approve, rejection_reason: rejectionReason }),
  linkProperty: (propertyId: string, residentId: string, relationshipType: RelationshipType) =>
    apiClient.post<PropertyResidentOut>("/residents/property-links", {
      property_id: propertyId, resident_id: residentId, relationship_type: relationshipType,
    }),
  unlinkProperty: (linkId: string) => apiClient.delete<PropertyResidentOut>(`/residents/property-links/${linkId}`),
  byProperty: (propertyId: string) => apiClient.get<PropertyResidentOut[]>(`/residents/by-property/${propertyId}`),
};

export const subadminsApi = {
  promote: (residentId: string, locationIds: string[]) =>
    apiClient.post<SubAdminScopeOut[]>("/subadmins/promote", { resident_id: residentId, location_ids: locationIds }),
  scopes: (subAdminId: string) => apiClient.get<SubAdminScopeOut[]>(`/subadmins/${subAdminId}/scopes`),
  assignScope: (subAdminId: string, locationId: string) =>
    apiClient.post<SubAdminScopeOut>(`/subadmins/${subAdminId}/scopes`, { location_id: locationId }),
  revokeScope: (scopeId: string) => apiClient.delete<SubAdminScopeOut>(`/subadmins/scopes/${scopeId}`),
  submitResignation: (reason?: string) => apiClient.post<RoleRequestOut>("/subadmins/resignation", { reason }),
  pendingResignations: () => apiClient.get<RoleRequestOut[]>("/subadmins/resignations/pending"),
  decideResignation: (requestId: string, approve: boolean, decisionReason?: string) =>
    apiClient.post<RoleRequestOut>(`/subadmins/resignations/${requestId}/decision`, { approve, decision_reason: decisionReason }),
};

export type { Role };
