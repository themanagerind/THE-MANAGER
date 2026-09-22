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

export const societiesApi = {
  signup: (input: {
    society_name: string; society_code: string; address?: string; city?: string; state?: string; pincode?: string;
    admin_full_name: string; admin_mobile: string; admin_email?: string;
  }) => apiClient.post<{ society_id: string; admin_user_id: string; message: string }>("/societies/signup", input),
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
