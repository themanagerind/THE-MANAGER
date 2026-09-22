import { useQuery } from "@tanstack/react-query";
import { paymentsApi } from "@/api/payments";
import { Loader, ErrorState } from "@/components/States";

export function ResidentWallet() {
  const walletQuery = useQuery({
    queryKey: ["wallet", "me"],
    queryFn: () => paymentsApi.myWallet().then((r) => r.data),
  });

  if (walletQuery.isLoading) return <Loader />;
  if (walletQuery.isError) return <ErrorState message="Couldn't load your wallet." onRetry={() => walletQuery.refetch()} />;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Wallet</h1>
      <div className="border border-line rounded p-6">
        <p className="text-xs text-navy-muted mb-1">Balance</p>
        <p className="text-3xl font-semibold text-navy">
          ₹{(walletQuery.data?.balance ?? 0).toLocaleString("en-IN")}
        </p>
      </div>
      <p className="text-sm text-navy-muted">
        This is a record of your paid maintenance amounts — a running credit ledger, not a spendable balance.
        It updates automatically whenever a maintenance payment is approved.
      </p>
    </div>
  );
}
