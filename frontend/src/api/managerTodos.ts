import { apiClient } from "@/api/client";
import type { TodoStatus } from "@/types/enums";

export interface TaskSuggestionOut {
  id: string;
  title: string;
  created_by: string | null;
  created_at: string;
}

export interface ManagerTodoOut {
  id: string;
  society_id: string;
  manager_id: string;
  task_suggestion_id: string;
  task_date: string;
  status: TodoStatus;
  assigned_by: string;
  completed_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

/** A Manager's recurring daily-duty checklist — Admin ticks these on once
 * (typically right after creating the Manager's staff account) and each
 * active one generates that day's actual to-do automatically, instead of
 * Admin calling `assign` every single day for the same repeating task. */
export interface ManagerDailyTaskOut {
  id: string;
  society_id: string;
  manager_id: string;
  task_suggestion_id: string;
  task_title: string;
  is_active: boolean;
  created_at: string;
}

export const managerTodosApi = {
  taskSuggestions: () => apiClient.get<TaskSuggestionOut[]>("/task-suggestions"),
  addTaskSuggestion: (title: string) => apiClient.post<TaskSuggestionOut>("/task-suggestions", { title }),
  list: (skip = 0, limit = 20) => apiClient.get<Page<ManagerTodoOut>>("/manager-todos", { params: { skip, limit } }),
  assign: (managerId: string, taskSuggestionId: string, taskDate: string) =>
    apiClient.post<ManagerTodoOut>("/manager-todos", { manager_id: managerId, task_suggestion_id: taskSuggestionId, task_date: taskDate }),
  updateStatus: (id: string, status: TodoStatus) =>
    apiClient.patch<ManagerTodoOut>(`/manager-todos/${id}/status`, { status }),

  dailyTasks: (managerId: string) => apiClient.get<ManagerDailyTaskOut[]>(`/managers/${managerId}/daily-tasks`),
  /** Replaces the Manager's whole daily checklist with exactly this set —
   * matches a checkbox form, which always submits its full current state. */
  setDailyTasks: (managerId: string, taskSuggestionIds: string[]) =>
    apiClient.put<ManagerDailyTaskOut[]>(`/managers/${managerId}/daily-tasks`, { task_suggestion_ids: taskSuggestionIds }),
};
