import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentsApi } from "@/api/payments";
import { walletRedemptionsApi, type RedemptionCodeOut } from "@/api/walletRedemptions";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { ShopNowButton } from "@/components/ShopNowButton";

export function ResidentWallet() {
  const queryClient = useQueryClient();
  const [redeemOpen, setRedeemOpen] = useState(false);
  const [justRedeemed, setJustRedeemed] = useState<RedemptionCodeOut | null>(null);

  const walletQuery = useQuery({
    queryKey: ["wallet", "me"],
    queryFn: () => paymentsApi.myWallet().then((r) => r.data),
  });
  const redemptionsQuery = useQuery({
    queryKey: ["wallet-redemptions", "mine"],
    queryFn: () => walletRedemptionsApi.mine().then((r) => r.data),
  });

  if (walletQuery.isLoading) return <Loader />;
  if (walletQuery.isError) return <ErrorState message="Couldn't load your wallet." onRetry={() => walletQuery.refetch()} />;

  const balance = walletQuery.data?.balance ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-navy">Wallet</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setRedeemOpen(true)} disabled={balance <= 0}>
            Redeem Points
          </Button>
          <ShopNowButton />
        </div>
      </div>
      <div className="border border-line rounded p-6">
        <p className="text-xs text-navy-muted mb-1">Balance</p>
        <p className="text-3xl font-semibold text-navy">₹{balance.toLocaleString("en-IN")}</p>
      </div>
      <p className="text-sm text-navy-muted">
        This is a record of your paid maintenance amounts — a running credit ledger, not a spendable balance.
        It updates automatically whenever a maintenance payment is approved.
      </p>

      <div>
        <h2 className="text-sm font-medium text-navy-muted mb-2">Redemption codes</h2>
        {redemptionsQuery.isLoading && <Loader />}
        {redemptionsQuery.isError && (
          <ErrorState message="Couldn't load your redemption codes." onRetry={() => redemptionsQuery.refetch()} />
        )}
        {redemptionsQuery.data && redemptionsQuery.data.items.length === 0 && (
          <EmptyState
            title="No redemption codes yet"
            description="Redeem points above to get a code you can use with a partner store."
          />
        )}
        {redemptionsQuery.data && redemptionsQuery.data.items.length > 0 && (
          <Table<RedemptionCodeOut>
            keyFor={(r) => r.id}
            columns={[
              { header: "Code", render: (r) => <span className="font-mono font-medium">{r.code}</span> },
              { header: "Amount", render: (r) => `₹${r.amount.toLocaleString("en-IN")}` },
              { header: "Status", render: (r) => <Badge status={r.is_used ? "USED" : "ACTIVE"}>{r.is_used ? "Used" : "Active"}</Badge> },
              { header: "Created", render: (r) => new Date(r.created_at).toLocaleDateString("en-IN") },
            ]}
            rows={redemptionsQuery.data.items}
          />
        )}
      </div>

      {redeemOpen && (
        <RedeemModal
          balance={balance}
          onClose={() => setRedeemOpen(false)}
          onSuccess={(redemption) => {
            setRedeemOpen(false);
            setJustRedeemed(redemption);
            void queryClient.invalidateQueries({ queryKey: ["wallet", "me"] });
            void queryClient.invalidateQueries({ queryKey: ["wallet-redemptions", "mine"] });
          }}
        />
      )}

      {justRedeemed && (
        <Modal open onClose={() => setJustRedeemed(null)} title="Your redemption code">
          <div className="space-y-4">
            <p className="text-sm text-navy-muted">
              Give this code to the store to redeem ₹{justRedeemed.amount.toLocaleString("en-IN")}. It can only be
              used once.
            </p>
            <p className="text-center text-2xl font-mono font-semibold text-navy border border-line rounded py-4">
              {justRedeemed.code}
            </p>
            <div className="flex justify-end">
              <Button onClick={() => setJustRedeemed(null)}>Done</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function RedeemModal({
  balance, onClose, onSuccess,
}: { balance: number; onClose: () => void; onSuccess: (redemption: RedemptionCodeOut) => void }) {
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const redeem = useMutation({
    mutationFn: () => walletRedemptionsApi.create(Number(amount)).then((r) => r.data),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't redeem that amount.")),
  });

  const parsed = Number(amount);
  const valid = amount.trim() !== "" && parsed > 0 && parsed <= balance;

  return (
    <Modal open onClose={onClose} title="Redeem points">
      <div className="space-y-4">
        <p className="text-sm text-navy-muted">Available balance: ₹{balance.toLocaleString("en-IN")}</p>
        <Input
          label="Amount to redeem"
          type="number"
          min={1}
          max={balance}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="e.g. 500"
          error={amount.trim() !== "" && !valid ? `Enter an amount between 1 and ${balance}` : undefined}
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose} disabled={redeem.isPending}>Cancel</Button>
          <Button loading={redeem.isPending} disabled={!valid} onClick={() => redeem.mutate()}>
            Redeem
          </Button>
        </div>
      </div>
    </Modal>
  );
}
