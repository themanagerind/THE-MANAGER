import { apiClient } from "@/api/client";
import type { HouseType, LocationType, UserStatus } from "@/types/enums";

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
  /** Optional and all-or-nothing (Section 4 dual-role: ADMIN+RESIDENT) —
   * describes a unit the Admin also owns in this society. Backend
   * creates it as a brand-new property with the Admin as Owner; an
   * existing unit, or a Tenant relationship, goes through
   * residentsApi.linkSelf after approval instead. */
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
