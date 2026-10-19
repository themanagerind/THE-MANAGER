import { apiClient } from "@/api/client";

export interface RedemptionCodeOut {
  id: string;
  code: string;
  amount: number;
  is_used: boolean;
  used_at: string | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const walletRedemptionsApi = {
  /** Transfers `amount` points from the Resident's own wallet into the
   * Platform Owner's Master Wallet and returns a short, typeable code —
   * the voucher a Resident hands to Showcase (see ShopNowButton for the
   * newer, no-manual-code prefill flow; this is the fallback/manual path
   * backing it, and what the code is actually redeemed against). */
  create: (amount: number) => apiClient.post<RedemptionCodeOut>("/wallet-redemptions", { amount }),

  mine: (skip = 0, limit = 20) =>
    apiClient.get<Page<RedemptionCodeOut>>("/wallet-redemptions/mine", { params: { skip, limit } }),
};
