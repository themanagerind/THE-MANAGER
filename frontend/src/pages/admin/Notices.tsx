import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { noticesApi } from "@/api/notices";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";

export function AdminNotices() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

  const noticesQuery = useQuery({
    queryKey: ["admin", "notices"],
    queryFn: () => noticesApi.list().then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Notices</h1>
        <Button onClick={() => setCreating(true)}>Post notice</Button>
      </div>

      {noticesQuery.isLoading && <Loader />}
      {noticesQuery.isError && (
        <ErrorState message="Couldn't load notices." onRetry={() => noticesQuery.refetch()} />
      )}
      {noticesQuery.data && noticesQuery.data.items.length === 0 && (
        <EmptyState title="No notices yet" description="Post an announcement for every Resident to see." />
      )}

      <div className="space-y-3">
        {noticesQuery.data?.items.map((n) => (
          <div key={n.id} className="border border-line rounded p-4">
            <div className="flex items-center justify-between mb-1">
              <h2 className="font-medium text-ink">{n.title}</h2>
              <span className="text-xs text-navy-muted">{new Date(n.created_at).toLocaleDateString("en-IN")}</span>
            </div>
            <p className="text-sm text-navy-muted whitespace-pre-wrap">{n.content}</p>
          </div>
        ))}
      </div>

      {creating && (
        <CreateNoticeModal
          onClose={() => setCreating(false)}
          onSuccess={() => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "notices"] });
          }}
        />
      )}
    </div>
  );
}

function CreateNoticeModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => noticesApi.create(title.trim(), content.trim()),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't post this notice.")),
  });

  return (
    <Modal open onClose={onClose} title="Post notice">
      <div className="space-y-4">
        <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Content</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={create.isPending}
            disabled={!title.trim() || !content.trim()}
            onClick={() => create.mutate()}
          >
            Post
          </Button>
        </div>
      </div>
    </Modal>
  );
}
