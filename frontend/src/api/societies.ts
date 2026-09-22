import { apiClient } from "@/api/client";
import type { HouseType, LocationType, SocietyStatus } from "@/types/enums";

export interface SocietyOut {
  id: string;
  name: string;
  code: string;
  status: SocietyStatus;
  address: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  created_at: string;
}

export interface SocietyLocationOut {
  id: string;
  society_id: string;
  name: string;
  location_type: LocationType;
  created_at: string;
}

export interface SocietyLookupOut {
  id: string;
  name: string;
}

export const societiesApi = {
  /** Platform Owner creates a society directly from their dashboard —
   * the only way a society comes into existence now. ACTIVE immediately. */
  create: (input: { name: string; code: string; address?: string; city?: string; state?: string; pincode?: string }) =>
    apiClient.post<SocietyOut>("/societies", input),
  /** Public — used by the Admin/Resident signup forms to resolve a
   * society code to its id/name before submitting. */
  lookup: (code: string) => apiClient.get<SocietyLookupOut>(`/societies/lookup/${encodeURIComponent(code)}`),
  list: () => apiClient.get<SocietyOut[]>("/societies"),
  approve: (id: string) => apiClient.post<SocietyOut>(`/societies/${id}/approve`),
  updateStatus: (id: string, status: SocietyStatus) =>
    apiClient.patch<SocietyOut>(`/societies/${id}/status`, { status }),
};

export const locationsApi = {
  list: () => apiClient.get<SocietyLocationOut[]>("/properties/locations"),
  create: (name: string, locationType: LocationType) =>
    apiClient.post<SocietyLocationOut>("/properties/locations", { name, location_type: locationType }),
};

export const propertyAdminApi = {
  create: (locationId: string, houseNumber: string, houseType: HouseType, floorNumber?: number) =>
    apiClient.post("/properties", { location_id: locationId, house_number: houseNumber, house_type: houseType, floor_number: floorNumber }),
};
