export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Status = 'todo' | 'in_progress' | 'done'
export type Priority = 'LOW' | 'NORMAL' | 'HIGH'

export const PRIORITIES: { value: Priority; label: string }[] = [
  { value: 'HIGH', label: '높음' },
  { value: 'NORMAL', label: '보통' },
  { value: 'LOW', label: '낮음' },
]

export interface Task {
  id: number
  title: string
  description: string | null
  due_date: string | null
  priority: Priority
  status: Status
  created_at: string
  is_overdue: boolean
}

export interface User {
  id: number
  email: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number) {
    super(String(status))
    this.status = status
  }
}

// 로그인이 필요하다는 응답(401)을 받으면 화면이 로그인으로 보내도록 알린다.
let onUnauthorized: () => void = () => {}
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  if (res.status === 401 && !path.startsWith('/api/auth/login') && !path.startsWith('/api/auth/signup')) {
    onUnauthorized()
  }
  if (!res.ok) throw new ApiError(res.status)
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

export interface Suggestion {
  priority: Priority
  due_date: string | null
  reason: string
}

// 제안만 받아 온다. 서버는 저장하지 않는다.
export const suggestTask = (title: string, description: string) =>
  request<Suggestion>('/api/tasks/suggest', { method: 'POST', body: JSON.stringify({ title, description }) })

export interface GeneratedTask {
  title: string
  description: string
  priority: Priority
  due_date: string | null
}

// 주제에 맞는 Task 후보만 받아 온다. 서버는 저장하지 않는다.
export const generateTasks = (topic: string, description: string) =>
  request<{ tasks: GeneratedTask[]; reason: string }>('/api/tasks/generate', {
    method: 'POST',
    body: JSON.stringify({ topic, description }),
  })

export const deleteTask = (id: number) => request<void>(`/api/tasks/${id}`, { method: 'DELETE' })

export const getMe = () => request<User>('/api/auth/me')

export const signup = (email: string, password: string) =>
  request<User>('/api/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) })

export const login = (email: string, password: string) =>
  request<User>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })

export const logout = () => request<void>('/api/auth/logout', { method: 'POST' })
