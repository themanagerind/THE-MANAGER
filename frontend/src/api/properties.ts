import { apiClient } from "@/api/client";
import type { HouseType, RelationshipType } from "@/types/enums";

export interface PropertyResidentLink {
  id: string;
  property_id: string;
  resident_id: string;
  relationship_type: RelationshipType;
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
}

export interface PropertyOut {
  id: string;
  society_id: string;
  location_id: string;
  house_number: string;
  house_type: HouseType;
  floor_number: number | null;
  /** BUNGALOW-only — storeys built above the (always-implied) ground
   * floor; always 0 for FLAT. */
  floors_above_ground: number;
  status: string;
  created_at: string;
  /** Whether an active Resident (owner/tenant) is currently linked —
   * powers the Structure Overview diagram's occupied/vacant coloring. */
  is_occupied: boolean;
}

export const propertiesApi = {
  /** Section 12 — a Resident can own/rent multiple houses. */
  myLinks: (residentId: string) => apiClient.get<PropertyResidentLink[]>(`/residents/${residentId}/properties`),

  list: () => apiClient.get<PropertyOut[]>("/properties"),
};
