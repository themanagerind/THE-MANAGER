import { apiClient } from "@/api/client";

export interface UploadFileOut {
  /** A storage key — never a directly fetchable URL. Pass it straight
   * through to whichever create/submit call expects it. */
  file_url: string;
}

export const uploadsApi = {
  expenseBillImage: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<UploadFileOut>("/uploads/expense-bill-image", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};
