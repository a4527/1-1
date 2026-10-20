export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Status = 'todo' | 'in_progress' | 'done'
export type Priority = 'urgent' | 'normal' | 'low'

export interface Task {
  id: number
  title: string
  description: string | null
  due_date: string | null
  priority: Priority
  status: Status
  created_at: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  if (!res.ok) throw new Error(String(res.status))
  return res.status === 204 ? (undefined as T) : res.json()
}

export const listTasks = () => request<Task[]>('/api/tasks')

export const createTask = (title: string) =>
  request<Task>('/api/tasks', { method: 'POST', body: JSON.stringify({ title }) })

export interface TaskEdit {
  title: string
  description: string | null
  due_date: string | null
  priority: Priority
}

export const updateTask = (id: number, body: TaskEdit | { status: Status }) =>
  request<Task>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(body) })

export const deleteTask = (id: number) => request<void>(`/api/tasks/${id}`, { method: 'DELETE' })
