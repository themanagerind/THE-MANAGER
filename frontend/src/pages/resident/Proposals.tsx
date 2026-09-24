import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthContext";
import { proposalsApi, type ProposalOut } from "@/api/proposals";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";

export function ResidentProposals() {
  const [detailId, setDetailId] = useState<string | null>(null);
  const proposalsQuery = useQuery({ queryKey: ["proposals"], queryFn: () => proposalsApi.list().then((r) => r.data) });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Proposals</h1>

      {proposalsQuery.isLoading && <Loader />}
      {proposalsQuery.isError && <ErrorState message="Couldn't load proposals." onRetry={() => proposalsQuery.refetch()} />}
      {proposalsQuery.data && proposalsQuery.data.items.length === 0 && (
        <EmptyState title="No proposals yet" description="When the Admin opens a vote, it'll appear here." />
      )}

      <div className="space-y-3">
        {proposalsQuery.data?.items.map((p: ProposalOut) => (
          <button
            key={p.id}
            onClick={() => setDetailId(p.id)}
            className="w-full text-left border border-line rounded p-4 hover:border-navy transition-colors"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-ink">{p.title}</span>
              <Badge status={p.status}>{p.status}</Badge>
            </div>
            <p className="text-xs text-navy-muted">{p.scope_type === "SOCIETY" ? "Whole society" : p.scope_type}</p>
          </button>
        ))}
      </div>

      {detailId && <ProposalDetailModal id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function ProposalDetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { activeRole } = useAuth();
  // Backend 403s a plain Resident on this endpoint (governance oversight
  // only — a neighbor's individual vote isn't public) — a Sub-admin
  // shares this page/modal too (/subadmin/proposals), so only fetch it
  // for them.
  const canSeeHistory = activeRole === "SUB_ADMIN";
  const [error, setError] = useState<string | null>(null);
  const detailQuery = useQuery({ queryKey: ["proposal-detail", id], queryFn: () => proposalsApi.detail(id).then((r) => r.data) });
  const historyQuery = useQuery({
    queryKey: ["proposal-history", id],
    queryFn: () => proposalsApi.history(id).then((r) => r.data),
    enabled: canSeeHistory,
  });

  const vote = useMutation({
    mutationFn: (v: "APPROVE" | "REJECT") => proposalsApi.vote(id, v),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["proposal-detail", id] });
      void queryClient.invalidateQueries({ queryKey: ["proposals"] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-history", id] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't cast your vote.")),
  });

  return (
    <Modal open onClose={onClose} title={detailQuery.data?.proposal.title ?? "Proposal"}>
      {detailQuery.isLoading && <Loader />}
      {detailQuery.data && (
        <div className="space-y-4">
          <p className="text-sm text-navy-muted whitespace-pre-wrap">{detailQuery.data.proposal.description}</p>

          <div className="space-y-2 text-sm">
            <ThresholdBar
              label="Residents"
              percent={detailQuery.data.resident_percent}
              threshold={90}
              met={detailQuery.data.resident_threshold_met}
            />
            <ThresholdBar
              label="Sub-admins"
              percent={detailQuery.data.subadmin_percent}
              threshold={80}
              met={detailQuery.data.subadmin_threshold_met}
            />
          </div>

          {detailQuery.data.proposal.status === "WITHDRAWN" && detailQuery.data.proposal.withdrawn_at && (
            <p className="text-xs text-navy-muted">
              Withdrawn by your Admin on {new Date(detailQuery.data.proposal.withdrawn_at).toLocaleString("en-IN")} —
              voting is closed.
            </p>
          )}

          {error && <p className="text-sm text-danger">{error}</p>}

          {detailQuery.data.proposal.status === "OPEN" && (
            <div className="space-y-2 pt-2">
              {detailQuery.data.my_vote && (
                <p className="text-sm text-success text-right">
                  ✓ You voted {detailQuery.data.my_vote === "APPROVE" ? "Approve" : "Reject"} — you can change it
                  below until the vote closes.
                </p>
              )}
              <div className="flex gap-2 justify-end">
                <Button
                  variant={detailQuery.data.my_vote === "REJECT" ? "danger" : "secondary"}
                  loading={vote.isPending && vote.variables === "REJECT"}
                  disabled={vote.isPending}
                  onClick={() => vote.mutate("REJECT")}
                >
                  {detailQuery.data.my_vote === "REJECT" ? "✓ Rejected" : "Reject"}
                </Button>
                <Button
                  variant={detailQuery.data.my_vote === "REJECT" ? "secondary" : "primary"}
                  loading={vote.isPending && vote.variables === "APPROVE"}
                  disabled={vote.isPending}
                  onClick={() => vote.mutate("APPROVE")}
                >
                  {detailQuery.data.my_vote === "APPROVE" ? "✓ Approved" : "Approve"}
                </Button>
              </div>
            </div>
          )}

          {canSeeHistory && (
            <div className="pt-2 border-t border-line">
              <h3 className="text-xs font-medium text-navy-muted mb-2">Vote history</h3>
              {historyQuery.isLoading && <Loader />}
              {historyQuery.data && historyQuery.data.length === 0 && (
                <p className="text-xs text-navy-muted">No votes cast yet.</p>
              )}
              {historyQuery.data && historyQuery.data.length > 0 && (
                <ul className="space-y-1.5 max-h-40 overflow-y-auto">
                  {historyQuery.data.map((h) => (
                    <li key={h.id} className="text-xs text-navy-muted flex items-center justify-between gap-2">
                      <span>
                        <span className="text-ink font-medium">{h.voter_name}</span>{" "}
                        {h.old_vote ? `changed ${h.old_vote} → ${h.new_vote}` : `voted ${h.new_vote}`}
                      </span>
                      <span className="shrink-0">{new Date(h.changed_at).toLocaleString("en-IN")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function ThresholdBar({ label, percent, threshold, met }: { label: string; percent: number; threshold: number; met: boolean }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-navy-muted mb-1">
        <span>{label} — needs {threshold}%</span>
        <span className={met ? "text-success" : ""}>{percent.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-line rounded overflow-hidden">
        <div
          className={`h-full ${met ? "bg-success" : "bg-navy"}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}
