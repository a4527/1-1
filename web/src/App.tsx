import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { createTask, listTasks, updateTask } from './api'
import EditModal from './EditModal'
import type { Status, Task } from './api'

const COLUMNS: { status: Status; label: string }[] = [
  { status: 'todo', label: '할 일' },
  { status: 'in_progress', label: '진행 중' },
  { status: 'done', label: '완료' },
]

const STATUS_LABEL = Object.fromEntries(COLUMNS.map((c) => [c.status, c.label]))

const PRIORITY_LABEL = { urgent: '임박', normal: '보통', low: '여유' }

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [title, setTitle] = useState('')
  const [titleError, setTitleError] = useState('')
  const [creating, setCreating] = useState(false)
  const [busyIds, setBusyIds] = useState<number[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const editing = tasks.find((t) => t.id === editingId)

  useEffect(() => {
    listTasks().then(setTasks)
  }, [])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      setTitleError('제목을 입력해 주세요.')
      return
    }
    setCreating(true)
    try {
      const created = await createTask(title.trim())
      setTasks((prev) => [...prev, created])
      setTitle('')
    } finally {
      setCreating(false)
    }
  }

  async function handleStatus(task: Task, status: Status) {
    setBusyIds((prev) => [...prev, task.id])
    try {
      const updated = await updateTask(task.id, { status })
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
    } finally {
      setBusyIds((prev) => prev.filter((id) => id !== task.id))
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Task Flow</h1>
        <form onSubmit={handleCreate}>
          <input
            autoFocus
            value={title}
            maxLength={100}
            placeholder="새 Task 제목을 입력하세요"
            onChange={(e) => {
              setTitle(e.target.value)
              setTitleError('')
            }}
          />
          <button type="submit" disabled={creating}>
            등록
          </button>
          {titleError && <p className="field-error">{titleError}</p>}
        </form>
      </header>
      <main className="board">
        {COLUMNS.map(({ status, label }) => {
          const cards = tasks.filter((t) => t.status === status)
          return (
            <section className="column" key={status}>
              <h2>
                {label} ({cards.length})
              </h2>
              <div className="cards">
                {cards.map((t) => (
                  <article className="card" key={t.id} onClick={() => setEditingId(t.id)}>
                    <h3>{t.title}</h3>
                    <span className={`priority ${t.priority}`}>{PRIORITY_LABEL[t.priority]}</span>
                    {t.due_date && <p className="due">{t.due_date}</p>}
                    <div className="status-buttons">
                      {COLUMNS.map((c) => (
                        <button
                          key={c.status}
                          disabled={t.status === c.status || busyIds.includes(t.id)}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleStatus(t, c.status)
                          }}
                          aria-label={`${t.title}: ${STATUS_LABEL[c.status]}(으)로 변경`}
                        >
                          {c.label}
                        </button>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )
        })}
      </main>
      {editing && (
        <EditModal
          key={editing.id}
          task={editing}
          onClose={() => setEditingId(null)}
          onSaved={(saved) => {
            setTasks((prev) => prev.map((t) => (t.id === saved.id ? saved : t)))
            setEditingId(null)
          }}
          onDeleted={(id) => {
            setTasks((prev) => prev.filter((t) => t.id !== id))
            setEditingId(null)
          }}
        />
      )}
    </div>
  )
}

export default App
