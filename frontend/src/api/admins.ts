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
  /** Section 4 dual-role (ADMIN+RESIDENT) — OPTIONAL (user-requested: an
   * Admin no longer has to pick a unit, or be asked whether they have
   * one, at signup). If given, both fields must be given together, same
   * picker Resident signup uses (societiesApi.publicProperties/
   * publicLocations). If omitted, the Admin can link one later from the
   * Properties page ("Link as Resident" — POST /residents/self-link),
   * which grants the RESIDENT role automatically at that point. */
  existing_property_id?: string;
  existing_property_relationship?: RelationshipType;
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
