import { apiClient } from "@/api/client";
import { enqueue } from "@/api/offlineQueue";
import type { Page } from "@/types/enums";
import type { MaintenanceDueStatus, PaymentMethod, PaymentStatus, ProofType } from "@/types/enums";

export interface MaintenanceDueOut {
  id: string;
  society_id: string;
  property_id: string;
  amount: number;
  due_date: string;
  status: MaintenanceDueStatus;
  billing_month: string;
  generated_at: string;
}

export interface PaymentOut {
  id: string;
  society_id: string;
  maintenance_due_id: string;
  property_id: string;
  resident_id: string;
  payment_method: PaymentMethod;
  amount: number;
  status: PaymentStatus;
  reference_number: string | null;
  paid_marked_at: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface SubmitPaymentInput {
  maintenance_due_id: string;
  payment_method: PaymentMethod;
  reference_number?: string;
  proof_type?: ProofType;
  proof_file_url?: string;
}

export interface WalletOut {
  id: string;
  resident_id: string;
  balance: number;
}

export interface PaymentProofOut {
  id: string;
  payment_id: string;
  proof_type: ProofType;
  file_url: string;
  uploaded_at: string;
  uploaded_by: string;
}

export const paymentsApi = {
  duesForProperty: (propertyId: string) =>
    apiClient.get<MaintenanceDueOut[]>(`/payments/maintenance-dues/by-property/${propertyId}`),

  /** Section 37: if the request fails because we're offline, the write is
   * queued (src/api/offlineQueue.ts) instead of surfacing an error — the
   * idempotency_key already included guarantees a safe replay later. */
  submit: async (input: SubmitPaymentInput) => {
    const body = { ...input, idempotency_key: crypto.randomUUID() };
    try {
      return await apiClient.post<PaymentOut>("/payments", body);
    } catch (e) {
      const isNetworkError = !(e as { response?: unknown })?.response;
      if (isNetworkError && !navigator.onLine) {
        await enqueue("post", "/payments", body);
        return { data: null, queued: true } as unknown as { data: PaymentOut };
      }
      throw e;
    }
  },

  myWallet: () => apiClient.get<WalletOut>("/payments/wallet/me"),

  /** Section 14.2/14.3 — real multipart upload (audit fix: the payment
   * screen previously just asked for a pasted URL). Returns a file_url to
   * pass as SubmitPaymentIn.proof_file_url. */
  uploadProof: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<{ file_url: string }>("/uploads/payment-proof", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  proofs: (paymentId: string) => apiClient.get<PaymentProofOut[]>(`/payments/${paymentId}/proofs`),

  // --- Admin/Sub-admin (Section 13.2, 13.3, 27) ---
  generateBills: (amount: number, billingMonth: string) =>
    apiClient.post<MaintenanceDueOut[]>("/payments/maintenance-dues/generate", {
      amount, billing_month: billingMonth,
    }),
  allDues: () => apiClient.get<MaintenanceDueOut[]>("/payments/maintenance-dues"),
  list: (skip: number, limit: number) =>
    apiClient.get<Page<PaymentOut>>("/payments", { params: { skip, limit } }),
  pending: () => apiClient.get<PaymentOut[]>("/payments/pending"),
  approve: (paymentId: string) => apiClient.post<PaymentOut>(`/payments/${paymentId}/approve`),
  reject: (paymentId: string, rejectionReason: string) =>
    apiClient.post<PaymentOut>(`/payments/${paymentId}/reject`, { rejection_reason: rejectionReason }),
  correct: (paymentId: string, newAmount: number, reason: string) =>
    apiClient.post<{ correction_id: string; payment_id: string; old_amount: number; new_amount: number; difference: number }>(
      `/payments/${paymentId}/correct`, { new_amount: newAmount, reason }
    ),
};
