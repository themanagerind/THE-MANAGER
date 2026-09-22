import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { managerTodosApi, type ManagerTodoOut } from "@/api/managerTodos";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import type { TodoStatus } from "@/types/enums";

/** One-step forward-only progression (backend: manager_todo_service
 * _ALLOWED_TRANSITIONS) — DONE is terminal, nothing to do from there. */
const nextStatus: Partial<Record<TodoStatus, TodoStatus>> = {
  PENDING: "IN_PROGRESS",
  IN_PROGRESS: "DONE",
};
const nextActionLabel: Partial<Record<TodoStatus, string>> = {
  PENDING: "Start",
  IN_PROGRESS: "Mark done",
};

export function ManagerTodos() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const [error, setError] = useState<string | null>(null);

  const todosQuery = useQuery({
    queryKey: ["manager", "todos", page],
    queryFn: () => managerTodosApi.list(page * pageSize, pageSize).then((r) => r.data),
  });

  const suggestionsQuery = useQuery({
    queryKey: ["manager", "task-suggestions"],
    queryFn: () => managerTodosApi.taskSuggestions().then((r) => r.data),
  });

  const titleById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of suggestionsQuery.data ?? []) map.set(s.id, s.title);
    return map;
  }, [suggestionsQuery.data]);

  const advance = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TodoStatus }) => managerTodosApi.updateStatus(id, status),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["manager", "todos"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update the task status.")),
  });

  const isLoading = todosQuery.isLoading || suggestionsQuery.isLoading;
  const isError = todosQuery.isError || suggestionsQuery.isError;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">My To-Dos</h1>

      {error && <p className="text-sm text-danger">{error}</p>}

      {isLoading && <Loader />}
      {isError && (
        <ErrorState
          message="Couldn't load your to-dos."
          onRetry={() => {
            void todosQuery.refetch();
            void suggestionsQuery.refetch();
          }}
        />
      )}
      {todosQuery.data && todosQuery.data.items.length === 0 && (
        <EmptyState title="No tasks assigned yet" description="Tasks assigned to you by the Admin will show up here." />
      )}
      {todosQuery.data && todosQuery.data.items.length > 0 && (
        <>
          <Table<ManagerTodoOut>
            keyFor={(t) => t.id}
            columns={[
              { header: "Task", render: (t) => <span className="font-medium">{titleById.get(t.task_suggestion_id) ?? "—"}</span> },
              { header: "Date", render: (t) => new Date(t.task_date).toLocaleDateString("en-IN") },
              { header: "Status", render: (t) => <Badge status={t.status}>{t.status.replace("_", " ")}</Badge> },
              {
                header: "",
                render: (t) => {
                  const target = nextStatus[t.status];
                  const label = nextActionLabel[t.status];
                  if (!target || !label) return null;
                  return (
                    <div className="flex justify-end">
                      <Button
                        variant="secondary"
                        loading={advance.isPending && advance.variables?.id === t.id}
                        onClick={() => advance.mutate({ id: t.id, status: target })}
                      >
                        {label}
                      </Button>
                    </div>
                  );
                },
              },
            ]}
            rows={todosQuery.data.items}
          />
          <div className="flex items-center justify-between text-sm text-navy-muted">
            <span>
              {todosQuery.data.total === 0
                ? "0 tasks"
                : `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, todosQuery.data.total)} of ${todosQuery.data.total}`}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <Button
                variant="secondary"
                disabled={(page + 1) * pageSize >= todosQuery.data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
