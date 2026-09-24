import { apiClient } from "@/api/client";
import type { RelationshipType, UserStatus } from "@/types/enums";

export interface AdminOut {
  id: string;
  society_id: string | null;
  full_name: string;
  mobile: string;
  email: string | null;
  status: UserStatus;
  created_at: string;
}

export interface AdminSignupInput {
  full_name: string;
  mobile: string;
  email?: string;
  society_id: string;
  /** Section 4 dual-role (ADMIN+RESIDENT) — mandatory: every Admin also
   * links to a real unit already on record (Owner or Tenant), same
   * picker Resident signup uses (societiesApi.publicProperties/
   * publicLocations). There's no "describe a brand-new unit" option —
   * the Platform Owner is expected to have mapped the society's
   * structure before an Admin signs up against it. */
  existing_property_id: string;
  existing_property_relationship: RelationshipType;
}

export const adminsApi = {
  /** Public — no auth required. Targets an EXISTING, ACTIVE society
   * (created by the Platform Owner) and waits for Platform Owner
   * approval — unlike Resident signup, which the society's own Admin
   * approves. */
  signup: (input: AdminSignupInput) => apiClient.post<AdminOut>("/admins/signup", input),
  pending: () => apiClient.get<AdminOut[]>("/admins/pending"),
  decideApproval: (id: string, approve: boolean) =>
    apiClient.post<AdminOut>(`/admins/${id}/approval`, { approve }),
};
