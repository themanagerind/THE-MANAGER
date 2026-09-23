import { apiClient } from "@/api/client";
import type { PropertyOut } from "@/api/properties";
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
  latitude: number | null;
  longitude: number | null;
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

export interface SocietySearchResultOut {
  id: string;
  name: string;
  city: string | null;
}

export interface SocietyCreateInput {
  name: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  /** Optional, along with latitude/longitude below — a Platform Owner
   * can add Wings/Rows right at creation, or leave this empty and let
   * the Admin add them later from the Properties page. `code` is never
   * sent — the backend auto-generates a guaranteed-unique one. */
  locations?: { name: string; location_type: LocationType }[];
  /** GPS pin — optional, but both-or-neither (backend rejects a lone
   * coordinate). */
  latitude?: number;
  longitude?: number;
}

export interface SocietyUpdateInput {
  name: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  latitude?: number;
  longitude?: number;
}

export const societiesApi = {
  /** Platform Owner creates a society directly from their dashboard —
   * the only way a society comes into existence now. ACTIVE immediately. */
  create: (input: SocietyCreateInput) => apiClient.post<SocietyOut>("/societies", input),
  /** Platform Owner edits name/address/city/state/pincode after creation
   * — `code` stays fixed (see backend SocietyUpdateIn's docstring). */
  update: (id: string, input: SocietyUpdateInput) => apiClient.patch<SocietyOut>(`/societies/${id}`, input),
  /** Public — used by the Admin/Resident signup forms to resolve a
   * society code to its id/name before submitting. */
  lookup: (code: string) => apiClient.get<SocietyLookupOut>(`/societies/lookup/${encodeURIComponent(code)}`),
  /** Public — name-search picker alternative to typing the exact code.
   * Backend enforces a 3-char minimum and rate-limits by IP; never
   * returns `code` (see SocietySearchResultOut). */
  search: (q: string) => apiClient.get<SocietySearchResultOut[]>("/societies/search", { params: { q } }),
  list: () => apiClient.get<SocietyOut[]>("/societies"),
  approve: (id: string) => apiClient.post<SocietyOut>(`/societies/${id}/approve`),
  updateStatus: (id: string, status: SocietyStatus) =>
    apiClient.patch<SocietyOut>(`/societies/${id}/status`, { status }),
  /** Platform Owner viewing/adding a society's Wings/Rows straight from
   * the Societies page's Edit modal — same data the Admin manages from
   * their own Properties page, reachable without switching roles. */
  listLocations: (id: string) => apiClient.get<SocietyLocationOut[]>(`/societies/${id}/locations`),
  addLocation: (id: string, name: string, locationType: LocationType) =>
    apiClient.post<SocietyLocationOut>(`/societies/${id}/locations`, { name, location_type: locationType }),
  /** Renaming is always allowed; changing WING<->ROW only succeeds while
   * no Property yet points at it (backend rejects with a 409 naming how
   * many properties are in the way). */
  updateLocation: (societyId: string, locationId: string, name: string, locationType: LocationType) =>
    apiClient.patch<SocietyLocationOut>(`/societies/${societyId}/locations/${locationId}`, {
      name, location_type: locationType,
    }),
  /** Bulk-generates every tower/floor/flat combination in one request —
   * one Wing per entry in `wings`, each with its own floor count and
   * flats/floor (a taller tower next to a shorter one is fine). A Wing
   * with no name gets an auto-generated one server-side ("Tower N").
   * `floor_overrides` lists per-floor exceptions to that Wing's default
   * flats_per_floor (e.g. a ground floor with fewer flats). */
  generateFlatsStructure: (
    id: string,
    wings: {
      name?: string;
      floor_count: number;
      flats_per_floor: number;
      floor_overrides?: { floor_number: number; flats: number }[];
    }[]
  ) => apiClient.post<PropertyOut[]>(`/societies/${id}/structure/flats`, { wings }),
  /** Bulk-generates every row/house at ground-floor-only — extra storeys
   * per house are set afterward via updatePropertyFloors. */
  generateBungalowStructure: (id: string, rowCount: number, housesPerRow: number) =>
    apiClient.post<PropertyOut[]>(`/societies/${id}/structure/bungalows`, {
      row_count: rowCount, houses_per_row: housesPerRow,
    }),
  listProperties: (id: string) => apiClient.get<PropertyOut[]>(`/societies/${id}/properties`),
  updatePropertyFloors: (societyId: string, propertyId: string, floorsAboveGround: number) =>
    apiClient.patch<PropertyOut>(`/societies/${societyId}/properties/${propertyId}/floors`, {
      floors_above_ground: floorsAboveGround,
    }),
  /** The Society Mapping page's Flats & Houses-mapping step — one Property
   * with a specific, hand-typed house_number on a chosen Wing + floor
   * (FLAT) or Row (BUNGALOW, no floor). */
  addProperty: (
    societyId: string, locationId: string, houseNumber: string, houseType: HouseType, floorNumber?: number
  ) =>
    apiClient.post<PropertyOut>(`/societies/${societyId}/properties`, {
      location_id: locationId, house_number: houseNumber, house_type: houseType, floor_number: floorNumber,
    }),
  /** Correcting a Wing/Row/floor/house-number typo made while mapping —
   * full replace, same shape as addProperty. */
  updateProperty: (
    societyId: string, propertyId: string, locationId: string, houseNumber: string, houseType: HouseType,
    floorNumber?: number
  ) =>
    apiClient.patch<PropertyOut>(`/societies/${societyId}/properties/${propertyId}`, {
      location_id: locationId, house_number: houseNumber, house_type: houseType, floor_number: floorNumber,
    }),
  /** Removing a wrongly-added Property — only succeeds while nothing else
   * (a Resident, a payment...) references it yet. */
  deleteProperty: (societyId: string, propertyId: string) =>
    apiClient.delete(`/societies/${societyId}/properties/${propertyId}`),
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
