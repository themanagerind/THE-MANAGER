import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountEntriesApi, type AccountEntryOut } from "@/api/accountEntries";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import type { EntryType } from "@/types/enums";

export function AdminAccounts() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AccountEntryOut | null>(null);

  const balanceQuery = useQuery({
    queryKey: ["admin", "account-balance"],
    queryFn: () => accountEntriesApi.balance().then((r) => r.data),
  });
  const entriesQuery = useQuery({
    queryKey: ["admin", "account-entries"],
    queryFn: () => accountEntriesApi.list().then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Accounts</h1>
        <Button onClick={() => setCreating(true)}>Add entry</Button>
      </div>

      {balanceQuery.data && (
        <div className="grid grid-cols-3 gap-3">
          <div className="border border-line rounded p-4">
            <p className="text-xs text-navy-muted mb-1">Income</p>
            <p className="text-lg font-semibold text-success">₹{balanceQuery.data.total_income.toLocaleString("en-IN")}</p>
          </div>
          <div className="border border-line rounded p-4">
            <p className="text-xs text-navy-muted mb-1">Expense</p>
            <p className="text-lg font-semibold text-danger">₹{balanceQuery.data.total_expense.toLocaleString("en-IN")}</p>
          </div>
          <div className="border border-line rounded p-4">
            <p className="text-xs text-navy-muted mb-1">Balance</p>
            <p className="text-lg font-semibold text-navy">₹{balanceQuery.data.balance.toLocaleString("en-IN")}</p>
          </div>
        </div>
      )}

      {entriesQuery.isLoading && <Loader />}
      {entriesQuery.isError && (
        <ErrorState message="Couldn't load account entries." onRetry={() => entriesQuery.refetch()} />
      )}
      {entriesQuery.data && entriesQuery.data.items.length === 0 && (
        <EmptyState title="No entries yet" description="Manual entries and auto-generated payment/expense entries show up here." />
      )}
      {entriesQuery.data && entriesQuery.data.items.length > 0 && (
        <Table<AccountEntryOut>
          keyFor={(e) => e.id}
          columns={[
            { header: "Heading", render: (e) => <span className="font-medium">{e.title}</span> },
            { header: "Type", render: (e) => <Badge status={e.entry_type === "INCOME" ? "PAID" : "REJECTED"}>{e.entry_type}</Badge> },
            { header: "Amount", render: (e) => `₹${e.amount.toLocaleString("en-IN")}` },
            { header: "Date", render: (e) => new Date(e.entry_date).toLocaleDateString("en-IN") },
            { header: "Source", render: (e) => (e.is_edited ? <Badge status="PENDING">Edited</Badge> : e.source) },
            {
              header: "",
              render: (e) =>
                e.source === "MANUAL" ? (
                  <div className="flex justify-end">
                    <Button variant="secondary" onClick={() => setEditing(e)}>Edit</Button>
                  </div>
                ) : null,
            },
          ]}
          rows={entriesQuery.data.items}
        />
      )}

      {creating && (
        <CreateEntryModal
          onClose={() => setCreating(false)}
          onSuccess={() => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "account-entries"] });
            void queryClient.invalidateQueries({ queryKey: ["admin", "account-balance"] });
          }}
        />
      )}

      {editing && (
        <EditEntryModal
          entry={editing}
          onClose={() => setEditing(null)}
          onSuccess={() => {
            setEditing(null);
            void queryClient.invalidateQueries({ queryKey: ["admin", "account-entries"] });
            void queryClient.invalidateQueries({ queryKey: ["admin", "account-balance"] });
          }}
        />
      )}
    </div>
  );
}

/**
 * Heading picker + inline "add a new heading" — same pattern as Staff's
 * Daily Tasks checklist: pick from the platform-global catalog (seeded
 * with headings universal to Indian housing-society bookkeeping, e.g.
 * "Lift Maintenance", "Society Maintenance Charges"), or type a new one
 * and it's usable immediately. Title is no longer free-typed on the
 * entry itself — it's always taken from the picked heading.
 *
 * Adding and renaming are both gated behind their own checkbox — left
 * unchecked, those fields stay disabled, so they can't be typed into by
 * accident (the "3000" mistake this whole thing started from). A
 * confirmation line appears after adding, and renaming is safe because
 * an entry's title is a snapshot taken when it was created/edited, so
 * it never retroactively touches an entry that already used a heading.
 */
function HeadingPicker({
  entryType, headingId, onChange,
}: { entryType: EntryType; headingId: string; onChange: (id: string) => void }) {
  const queryClient = useQueryClient();
  const [addingNew, setAddingNew] = useState(false);
  const [newHeadingTitle, setNewHeadingTitle] = useState("");
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [renameTitle, setRenameTitle] = useState("");

  const headingsQuery = useQuery({
    queryKey: ["admin", "account-headings", entryType],
    queryFn: () => accountEntriesApi.headings(entryType).then((r) => r.data),
  });

  const addHeading = useMutation({
    mutationFn: () => accountEntriesApi.addHeading(entryType, newHeadingTitle.trim()),
    onSuccess: (res) => {
      setNewHeadingTitle("");
      setAddingNew(false);
      setJustAdded(res.data.title);
      setError(null);
      onChange(res.data.id);
      void queryClient.invalidateQueries({ queryKey: ["admin", "account-headings"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add this heading.")),
  });

  const renameHeading = useMutation({
    mutationFn: () => accountEntriesApi.editHeading(headingId, renameTitle.trim()),
    onSuccess: () => {
      setRenaming(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "account-headings"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't rename this heading.")),
  });

  const selectedHeading = headingsQuery.data?.find((h) => h.id === headingId);

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm text-navy-muted mb-1">Heading</label>
        {headingsQuery.isLoading && <Loader />}
        {headingsQuery.isError && (
          <ErrorState message="Couldn't load headings." onRetry={() => headingsQuery.refetch()} />
        )}
        {headingsQuery.data && (
          <select
            value={headingId}
            onChange={(e) => {
              onChange(e.target.value);
              setJustAdded(null);
              setRenaming(false);
            }}
            className="w-full border border-line rounded px-3 py-2 text-sm"
          >
            <option value="">Select a heading</option>
            {headingsQuery.data.map((h) => (
              <option key={h.id} value={h.id}>{h.title}</option>
            ))}
          </select>
        )}
        {justAdded && (
          <p className="text-xs text-success mt-1">
            ✓ &quot;{justAdded}&quot; added and selected above as this entry&apos;s heading.
          </p>
        )}
      </div>

      {headingId && (
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={renaming}
              onChange={(e) => {
                setRenaming(e.target.checked);
                setRenameTitle(e.target.checked ? selectedHeading?.title ?? "" : "");
              }}
            />
            Rename the selected heading
          </label>
          {renaming && (
            <div className="flex gap-2 items-end border border-line rounded p-3 bg-paper">
              <div className="flex-1">
                <Input label="New name" value={renameTitle} onChange={(e) => setRenameTitle(e.target.value)} />
              </div>
              <Button
                variant="secondary"
                loading={renameHeading.isPending}
                disabled={!renameTitle.trim()}
                onClick={() => renameHeading.mutate()}
              >
                Save
              </Button>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={addingNew}
            onChange={(e) => {
              setAddingNew(e.target.checked);
              if (!e.target.checked) setNewHeadingTitle("");
            }}
          />
          Add a new heading
        </label>
        {addingNew && (
          <>
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <Input
                  label="Heading name"
                  value={newHeadingTitle}
                  onChange={(e) => {
                    setNewHeadingTitle(e.target.value);
                    setJustAdded(null);
                  }}
                  placeholder={entryType === "INCOME" ? "e.g. Interest on Fixed Deposit" : "e.g. Diwali Decoration"}
                />
              </div>
              <Button
                variant="secondary"
                loading={addHeading.isPending}
                disabled={!newHeadingTitle.trim()}
                onClick={() => addHeading.mutate()}
              >
                Add
              </Button>
            </div>
            <p className="text-xs text-navy-muted">
              Must contain letters — an amount by itself (like &quot;3000&quot;) isn&apos;t a valid heading.
            </p>
          </>
        )}
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}

function CreateEntryModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [entryType, setEntryType] = useState<EntryType>("INCOME");
  const [headingId, setHeadingId] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      accountEntriesApi.create({
        entry_type: entryType,
        heading_id: headingId,
        description: description.trim() || undefined,
        amount: Number(amount),
        entry_date: entryDate,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add this entry.")),
  });

  const validAmount = Number(amount) > 0;

  return (
    <Modal open onClose={onClose} title="Add account entry">
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Type</label>
          <select
            value={entryType}
            onChange={(e) => {
              setEntryType(e.target.value as EntryType);
              setHeadingId("");
            }}
            className="w-full border border-line rounded px-3 py-2 text-sm"
          >
            <option value="INCOME">Income</option>
            <option value="EXPENSE">Expense</option>
          </select>
        </div>

        <HeadingPicker entryType={entryType} headingId={headingId} onChange={setHeadingId} />

        <Input label="Amount" type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Input label="Date" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!headingId || !validAmount} onClick={() => create.mutate()}>
            Add
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function EditEntryModal({
  entry, onClose, onSuccess,
}: { entry: AccountEntryOut; onClose: () => void; onSuccess: () => void }) {
  const [headingId, setHeadingId] = useState(entry.heading_id ?? "");
  const [description, setDescription] = useState(entry.description ?? "");
  const [amount, setAmount] = useState(String(entry.amount));
  const [entryDate, setEntryDate] = useState(entry.entry_date.slice(0, 10));
  const [error, setError] = useState<string | null>(null);

  const edit = useMutation({
    mutationFn: () =>
      accountEntriesApi.edit(entry.id, {
        heading_id: headingId || undefined,
        description: description.trim() || undefined,
        amount: Number(amount),
        entry_date: entryDate,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't edit this entry.")),
  });

  const validAmount = Number(amount) > 0;

  return (
    <Modal open onClose={onClose} title={`Edit — ${entry.title}`}>
      <div className="space-y-4">
        <HeadingPicker entryType={entry.entry_type} headingId={headingId} onChange={setHeadingId} />

        <Input label="Amount" type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Input label="Date" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={edit.isPending} disabled={!validAmount} onClick={() => edit.mutate()}>
            Save
          </Button>
        </div>
      </div>
    </Modal>
  );
}
