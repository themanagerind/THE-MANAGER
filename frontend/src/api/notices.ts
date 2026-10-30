import { apiClient } from "@/api/client";

export interface NoticeOut {
  id: string;
  society_id: string;
  title: string;
  content: string;
  created_by: string;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const noticesApi = {
  list: (skip = 0, limit = 20) => apiClient.get<Page<NoticeOut>>("/notices", { params: { skip, limit } }),
  create: (title: string, content: string) => apiClient.post<NoticeOut>("/notices", { title, content }),
};
