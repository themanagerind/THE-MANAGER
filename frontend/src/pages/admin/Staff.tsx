import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffApi, type StaffOut } from "@/api/staff";
import { managerTodosApi } from "@/api/managerTodos";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Modal } from "@/components/Modal";

/**
 * Manager and Security Guard are third-party hired staff, not Residents —
 * unlike Admin/Resident signup there's no property link and no approval
 * wait: the Admin creating the account here IS the approval, same as
 * Sub-admin promotion is unilateral (see AssignSubAdmin.tsx, the closest
 * existing pattern this mirrors).
 */
export function AdminStaff() {
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [role, setRole] = useState<"MANAGER" | "SECURITY_GUARD">("MANAGER");
  const [error, setError] = useState<string | null>(null);
  const [dailyTasksFor, setDailyTasksFor] = useState<StaffOut | null>(null);

  const staffQueryKey = ["admin", "staff"];
  const staffQuery = useQuery({
    queryKey: staffQueryKey,
    queryFn: () => staffApi.list().then((r) => r.data),
  });

  const create = useMutation({
    mutationFn: () => staffApi.create({ full_name: fullName.trim(), mobile: mobile.trim(), role }),
    onSuccess: (res) => {
      setFullName("");
      setMobile("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: staffQueryKey });
      // Straight into the daily-duty checklist for a new Manager — that's
      // the whole point of creating the account, no separate step needed.
      if (res.data.role === "MANAGER") setDailyTasksFor(res.data);
    },
    onError: (e) => setError(apiErrorMessage(e, "Could not create this account.")),
  });

  const remove = useMutation({
    mutationFn: (userId: string) => staffApi.remove(userId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: staffQueryKey }),
  });

  function handleRemove(s: StaffOut) {
    if (window.confirm(`Remove ${s.full_name} as ${s.role === "MANAGER" ? "Manager" : "Security Guard"}?`)) {
      remove.mutate(s.id);
    }
  }

  const mobileValid = /^\d{10}$/.test(mobile.trim());

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Staff</h1>

      <div className="space-y-4 rounded border border-line bg-paper p-4 max-w-md">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Role</label>
          <select
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            value={role}
            onChange={(e) => setRole(e.target.value as "MANAGER" | "SECURITY_GUARD")}
          >
            <option value="MANAGER">Manager</option>
            <option value="SECURITY_GUARD">Security Guard</option>
          </select>
        </div>
        <Input label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <Input
          label="Mobile number"
          value={mobile}
          onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
          error={mobile && !mobileValid ? "Enter a valid 10-digit mobile number" : undefined}
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end">
          <Button
            loading={create.isPending}
            disabled={!fullName.trim() || !mobileValid}
            onClick={() => create.mutate()}
          >
            Add
          </Button>
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Current staff</h2>
        {staffQuery.isLoading && <Loader />}
        {staffQuery.isError && (
          <ErrorState message="Couldn't load staff." onRetry={() => staffQuery.refetch()} />
        )}
        {staffQuery.data && staffQuery.data.length === 0 && (
          <EmptyState title="No Manager or Security Guard accounts yet" />
        )}
        {staffQuery.data && staffQuery.data.length > 0 && (
          <Table<StaffOut>
            keyFor={(s) => s.id}
            columns={[
              { header: "Name", render: (s) => s.full_name },
              { header: "Mobile", render: (s) => s.mobile },
              { header: "Role", render: (s) => <Badge status={s.role}>{s.role === "MANAGER" ? "Manager" : "Security Guard"}</Badge> },
              {
                header: "",
                render: (s) => (
                  <div className="flex justify-end gap-3">
                    {s.role === "MANAGER" && (
                      <button
                        type="button"
                        onClick={() => setDailyTasksFor(s)}
                        className="text-xs text-navy underline"
                      >
                        Daily Tasks
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemove(s)}
                      disabled={remove.isPending}
                      className="text-xs text-danger underline"
                    >
                      Remove
                    </button>
                  </div>
                ),
              },
            ]}
            rows={staffQuery.data}
          />
        )}
      </section>

      {dailyTasksFor && (
        <DailyTasksModal manager={dailyTasksFor} onClose={() => setDailyTasksFor(null)} />
      )}
    </div>
  );
}

/**
 * The universal daily-duty checklist for one Manager — Admin ticks on
 * whichever of the catalog's tasks apply (or adds a new one), and Save
 * replaces the Manager's whole active set in one call. Each active task
 * then generates that day's to-do automatically on the Manager's side
 * (backend: manager_todo_service._ensure_todays_todos_generated) — Admin
 * never has to re-assign a repeating task day after day again.
 */
function DailyTasksModal({ manager, onClose }: { manager: StaffOut; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  const suggestionsQuery = useQuery({
    queryKey: ["admin", "task-suggestions"],
    queryFn: () => managerTodosApi.taskSuggestions().then((r) => r.data),
  });
  const currentQuery = useQuery({
    queryKey: ["admin", "daily-tasks", manager.id],
    queryFn: () => managerTodosApi.dailyTasks(manager.id).then((r) => r.data),
  });

  useEffect(() => {
    if (!initialized && currentQuery.data) {
      setChecked(new Set(currentQuery.data.filter((t) => t.is_active).map((t) => t.task_suggestion_id)));
      setInitialized(true);
    }
  }, [initialized, currentQuery.data]);

  const addTask = useMutation({
    mutationFn: (title: string) => managerTodosApi.addTaskSuggestion(title),
    onSuccess: (res) => {
      setNewTaskTitle("");
      setChecked((prev) => new Set(prev).add(res.data.id));
      void queryClient.invalidateQueries({ queryKey: ["admin", "task-suggestions"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add this task.")),
  });

  const save = useMutation({
    mutationFn: () => managerTodosApi.setDailyTasks(manager.id, [...checked]),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "daily-tasks", manager.id] });
      onClose();
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't save the checklist.")),
  });

  function toggle(taskId: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  const isLoading = suggestionsQuery.isLoading || currentQuery.isLoading;

  return (
    <Modal open onClose={onClose} title={`Daily Tasks — ${manager.full_name}`}>
      <div className="space-y-4">
        <p className="text-sm text-navy-muted">
          Only work that repeats every day. Tick whichever apply — each one shows up in{" "}
          {manager.full_name}&apos;s to-do list automatically, every day, until unticked.
        </p>

        {isLoading && <Loader />}
        {(suggestionsQuery.isError || currentQuery.isError) && (
          <ErrorState
            message="Couldn't load the task checklist."
            onRetry={() => {
              void suggestionsQuery.refetch();
              void currentQuery.refetch();
            }}
          />
        )}

        {suggestionsQuery.data && currentQuery.data && (
          <div className="max-h-64 overflow-y-auto space-y-2 border border-line rounded p-3">
            {suggestionsQuery.data.map((t) => (
              <label key={t.id} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={checked.has(t.id)}
                  onChange={() => toggle(t.id)}
                  className="h-4 w-4"
                />
                {t.title}
              </label>
            ))}
          </div>
        )}

        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <Input
              label="Add a new daily task"
              value={newTaskTitle}
              onChange={(e) => setNewTaskTitle(e.target.value)}
              placeholder="e.g. Swimming pool chlorine check"
            />
          </div>
          <Button
            variant="secondary"
            loading={addTask.isPending}
            disabled={!newTaskTitle.trim()}
            onClick={() => addTask.mutate(newTaskTitle.trim())}
          >
            Add
          </Button>
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
        </div>
      </div>
    </Modal>
  );
}
