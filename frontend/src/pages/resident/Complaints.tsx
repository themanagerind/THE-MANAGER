import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { complaintsApi, type ComplaintOut } from "@/api/complaints";
import { useActiveProperty } from "@/hooks/useActiveProperty";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { PropertySelector } from "@/components/PropertySelector";

const CATEGORIES = ["Plumbing", "Electrical", "Cleanliness", "Security", "Parking", "Other"];

export function ResidentComplaints() {
  const { activePropertyId, setActivePropertyId, options, hasMultipleProperties } = useActiveProperty();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const complaintsQuery = useQuery({
    queryKey: ["complaints", "mine"],
    queryFn: () => complaintsApi.list().then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Complaints</h1>
        <Button onClick={() => setShowCreate(true)}>New complaint</Button>
      </div>

      {complaintsQuery.isLoading && <Loader />}
      {complaintsQuery.isError && <ErrorState message="Couldn't load complaints." onRetry={() => complaintsQuery.refetch()} />}
      {complaintsQuery.data && complaintsQuery.data.length === 0 && (
        <EmptyState title="No complaints yet" description="Raise one if something needs attention." />
      )}
      {complaintsQuery.data && complaintsQuery.data.length > 0 && (
        <Table<ComplaintOut>
          keyFor={(c) => c.id}
          columns={[
            { header: "Title", render: (c) => <span className="font-medium">{c.title}</span> },
            { header: "Category", render: (c) => c.category },
            { header: "Status", render: (c) => <Badge status={c.status}>{c.status.replace("_", " ")}</Badge> },
            { header: "Raised", render: (c) => new Date(c.created_at).toLocaleDateString("en-IN") },
          ]}
          rows={complaintsQuery.data}
        />
      )}

      {showCreate && (
        <CreateComplaintModal
          properties={options}
          activePropertyId={activePropertyId}
          hasMultipleProperties={hasMultipleProperties}
          onPropertyChange={setActivePropertyId}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            void queryClient.invalidateQueries({ queryKey: ["complaints", "mine"] });
          }}
        />
      )}
    </div>
  );
}

function CreateComplaintModal({
  properties, activePropertyId, hasMultipleProperties, onPropertyChange, onClose, onSuccess,
}: {
  properties: { property_id: string; label: string }[];
  activePropertyId: string | null;
  hasMultipleProperties: boolean;
  onPropertyChange: (id: string) => void;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      complaintsApi.create({ property_id: activePropertyId!, category, title, description }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't submit the complaint.")),
  });

  return (
    <Modal open onClose={onClose} title="Raise a complaint">
      <div className="space-y-4">
        {hasMultipleProperties && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Property</label>
            <PropertySelector properties={properties} activePropertyId={activePropertyId} onChange={onPropertyChange} />
          </div>
        )}
        <div>
          <label className="block text-sm text-navy-muted mb-1">Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full border border-line rounded px-3 py-2 text-sm">
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full border border-line rounded px-3 py-2 text-sm"
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!title || !description} onClick={() => create.mutate()}>
            Submit
          </Button>
        </div>
      </div>
    </Modal>
  );
}
