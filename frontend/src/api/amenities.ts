import { apiClient } from "@/api/client";
import type { BookingStatus } from "@/types/enums";

export interface AmenityOut {
  id: string;
  society_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface AmenityBookingOut {
  id: string;
  society_id: string;
  amenity_id: string;
  property_id: string;
  resident_id: string;
  booking_date: string;
  start_time: string;
  end_time: string;
  status: BookingStatus;
  created_at: string;
}

export interface BookingCreateInput {
  amenity_id: string;
  property_id: string;
  booking_date: string;
  start_time: string;
  end_time: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const amenitiesApi = {
  list: () => apiClient.get<AmenityOut[]>("/amenities"),
  create: (name: string, description?: string) => apiClient.post<AmenityOut>("/amenities", { name, description }),
  bookings: (skip = 0, limit = 20) =>
    apiClient.get<Page<AmenityBookingOut>>("/amenities/bookings", { params: { skip, limit } }),
  createBooking: (input: BookingCreateInput) => apiClient.post<AmenityBookingOut>("/amenities/bookings", input),
  decideBooking: (id: string, approve: boolean) =>
    apiClient.post<AmenityBookingOut>(`/amenities/bookings/${id}/decision`, { approve }),
};
