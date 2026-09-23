import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { proposalsApi, type ProposalOut } from "@/api/proposals";
import { locationsApi } from "@/api/societies";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import type { ProposalScope } from "@/types/enums";

export function AdminProposals() {
  const [detailId, setDetailId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const queryClient = useQueryClient();

  const proposalsQuery = useQuery({
    queryKey: ["admin", "proposals"],
    queryFn: () => proposalsApi.list().then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Proposals</h1>
        <Button onClick={() => setCreating(true)}>Raise proposal</Button>
      </div>

      {proposalsQuery.isLoading && <Loader />}
      {proposalsQuery.isError && (
        <ErrorState message="Couldn't load proposals." onRetry={() => proposalsQuery.refetch()} />
      )}
      {proposalsQuery.data && proposalsQuery.data.items.length === 0 && (
        <EmptyState title="No proposals yet" description="Raise one to put a decision to a vote." />
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

      {creating && (
        <CreateProposalModal
          onClose={() => setCreating(false)}
          onSuccess={() => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "proposals"] });
          }}
        />
      )}
    </div>
  );
}

function ProposalDetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const detailQuery = useQuery({
    queryKey: ["admin", "proposal-detail", id],
    queryFn: () => proposalsApi.detail(id).then((r) => r.data),
  });

  const withdraw = useMutation({
    mutationFn: () => proposalsApi.withdraw(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "proposal-detail", id] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "proposals"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't withdraw this proposal.")),
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

          {error && <p className="text-sm text-danger">{error}</p>}

          {detailQuery.data.proposal.status === "OPEN" && (
            <div className="flex justify-end pt-2">
              <Button variant="secondary" loading={withdraw.isPending} onClick={() => withdraw.mutate()}>
                Withdraw
              </Button>
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

const SCOPES: ProposalScope[] = ["SOCIETY", "WING", "ROW"];

function CreateProposalModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [scopeType, setScopeType] = useState<ProposalScope>("SOCIETY");
  const [locationId, setLocationId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: ["admin", "locations"],
    queryFn: () => locationsApi.list().then((r) => r.data),
    enabled: scopeType !== "SOCIETY",
  });
  const matchingLocations = (locationsQuery.data ?? []).filter(
    (l) => l.location_type === scopeType
  );

  const create = useMutation({
    mutationFn: () =>
      proposalsApi.create({
        scope_type: scopeType,
        scope_location_id: scopeType === "SOCIETY" ? undefined : locationId,
        title: title.trim(),
        description: description.trim(),
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't raise this proposal.")),
  });

  const needsLocation = scopeType !== "SOCIETY";

  return (
    <Modal open onClose={onClose} title="Raise proposal">
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Scope</label>
          <select
            value={scopeType}
            onChange={(e) => {
              setScopeType(e.target.value as ProposalScope);
              setLocationId("");
            }}
            className="w-full border border-line rounded px-3 py-2 text-sm"
          >
            {SCOPES.map((s) => (
              <option key={s} value={s}>{s === "SOCIETY" ? "Whole society" : s}</option>
            ))}
          </select>
        </div>
        {needsLocation && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">
              {scopeType === "WING" ? "Wing" : "Row"}
            </label>
            <select
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              className="w-full border border-line rounded px-3 py-2 text-sm"
            >
              <option value="">Select {scopeType === "WING" ? "a wing" : "a row"}</option>
              {matchingLocations.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          </div>
        )}
        <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={create.isPending}
            disabled={!title.trim() || !description.trim() || (needsLocation && !locationId)}
            onClick={() => create.mutate()}
          >
            Raise
          </Button>
        </div>
      </div>
    </Modal>
  );
}
