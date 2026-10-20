import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { createTask, listTasks, updateTask } from './api'
import type { Status, Task } from './api'
import EditModal from './EditModal'

const COLUMNS: { status: Status; label: string; empty: string }[] = [
  { status: 'todo', label: '할 일', empty: '할 일이 없습니다.' },
  { status: 'in_progress', label: '진행 중', empty: '진행 중인 카드가 없습니다.' },
  { status: 'done', label: '완료', empty: '완료한 카드가 없습니다.' },
]

const STATUS_LABEL = Object.fromEntries(COLUMNS.map((c) => [c.status, c.label]))

const PRIORITY_LABEL = { urgent: '임박', normal: '보통', low: '여유' }

const FIRST_TASK_HINT = '위 입력창에 제목을 적어 첫 Task를 만들어 보세요.'
const LOAD_ERROR = '카드를 불러오지 못했습니다. API 서버가 켜져 있는지 확인하세요.'
const SAVE_ERROR = '저장하지 못했습니다. 다시 시도해 주세요.'

type LoadState = 'loading' | 'ready' | 'error'

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [alert, setAlert] = useState('')
  const [title, setTitle] = useState('')
  const [titleError, setTitleError] = useState('')
  const [creating, setCreating] = useState(false)
  const [busyIds, setBusyIds] = useState<number[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const editing = tasks.find((t) => t.id === editingId)

  const load = useCallback(() => {
    listTasks()
      .then((list) => {
        setTasks(list)
        setLoadState('ready')
      })
      .catch(() => setLoadState('error'))
  }, [])

  useEffect(load, [load])

  function reload() {
    setLoadState('loading')
    load()
  }

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
      setAlert('')
    } catch {
      setAlert(SAVE_ERROR)
    } finally {
      setCreating(false)
    }
  }

  async function handleStatus(task: Task, status: Status) {
    setBusyIds((prev) => [...prev, task.id])
    try {
      const updated = await updateTask(task.id, { status })
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
      setAlert('')
    } catch {
      setAlert(SAVE_ERROR)
    } finally {
      setBusyIds((prev) => prev.filter((id) => id !== task.id))
    }
  }

  function renderColumnBody(status: Status, cards: Task[], emptyText: string) {
    if (loadState === 'loading') return <p className="column-note">불러오는 중…</p>
    if (loadState === 'error') {
      if (status !== 'todo') return null
      return (
        <div className="column-note error">
          <p>{LOAD_ERROR}</p>
          <button onClick={reload}>다시 불러오기</button>
        </div>
      )
    }
    if (cards.length === 0) {
      const text = status === 'todo' && tasks.length === 0 ? FIRST_TASK_HINT : emptyText
      return <p className="column-note">{text}</p>
    }
    return cards.map((t) => (
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
    ))
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
          <button type="submit" disabled={creating || loadState !== 'ready'}>
            등록
          </button>
          {titleError && <p className="field-error">{titleError}</p>}
        </form>
      </header>
      {alert && (
        <div className="alert" role="alert">
          <span>⚠ {alert}</span>
          <button onClick={() => setAlert('')}>닫기</button>
        </div>
      )}
      <main className="board">
        {COLUMNS.map(({ status, label, empty }) => {
          const cards = tasks.filter((t) => t.status === status)
          const count = loadState === 'ready' ? cards.length : '-'
          return (
            <section className="column" key={status}>
              <h2>
                {label} ({count})
              </h2>
              <div className="cards">{renderColumnBody(status, cards, empty)}</div>
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
            setAlert('')
          }}
          onDeleted={(id) => {
            setTasks((prev) => prev.filter((t) => t.id !== id))
            setEditingId(null)
            setAlert('')
          }}
        />
      )}
    </div>
  )
}

export default App
