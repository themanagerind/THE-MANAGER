import { apiClient } from "@/api/client";
import type { HouseType, LocationType, RelationshipType, UserStatus } from "@/types/enums";

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
  /** Section 4 dual-role (ADMIN+RESIDENT) — two mutually-exclusive,
   * both-optional ways to describe a unit the Admin also lives in, right
   * at signup instead of a separate step after approval:
   * (1) existing_property_id/existing_property_relationship — pick a
   *     real unit already on record (Owner or Tenant), same picker
   *     Resident signup uses (societiesApi.publicProperties).
   * (2) property_location_name/... (all-or-nothing) — describe a
   *     brand-new unit not yet on record, Owner only. */
  existing_property_id?: string;
  existing_property_relationship?: RelationshipType;
  property_location_name?: string;
  property_location_type?: LocationType;
  house_number?: string;
  house_type?: HouseType;
  floor_number?: number;
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
