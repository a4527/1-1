import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { PRIORITIES, createTask, deleteTask, getMe, listTasks, logout, setUnauthorizedHandler, updateTask } from './api'
import type { Priority, Status, Task, User } from './api'
import BriefingCard from './BriefingCard'
import CommandPanel from './CommandPanel'
import EditModal from './EditModal'
import GeneratePanel from './GeneratePanel'
import Login from './Login'
import WeekPlanCard from './WeekPlanCard'
import { useGenerate } from './useGenerate'
import { useSuggest } from './useSuggest'

const COLUMNS: { status: Status; label: string; empty: string }[] = [
  { status: 'todo', label: '할 일', empty: '할 일이 없습니다.' },
  { status: 'in_progress', label: '진행 중', empty: '진행 중인 카드가 없습니다.' },
  { status: 'done', label: '완료', empty: '완료한 카드가 없습니다.' },
]

const PRIORITY_LABEL = { HIGH: '높음', NORMAL: '보통', LOW: '낮음' }

const FIRST_TASK_HINT = '위 입력창에 제목을 적어 첫 Task를 만들어 보세요.'
const LOAD_ERROR = '카드를 불러오지 못했습니다. API 서버가 켜져 있는지 확인하세요.'
const SAVE_ERROR = '저장하지 못했습니다. 다시 시도해 주세요.'
const DELETE_ERROR = '삭제하지 못했습니다. 다시 시도해 주세요.'
const EXTRA_ERROR = 'Task는 만들었지만 설명·마감일·우선순위를 저장하지 못했습니다. 카드를 눌러 수정해 주세요.'

type LoadState = 'loading' | 'ready' | 'error'

function Board({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [alert, setAlert] = useState('')
  const [title, setTitle] = useState('')
  const [titleError, setTitleError] = useState('')
  const [description, setDescription] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [priority, setPriority] = useState<Priority>('NORMAL')
  const [creating, setCreating] = useState(false)
  const suggest = useSuggest((s) => {
    setPriority(s.priority)
    setDueDate(s.due_date ?? '')
  })
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

  const gen = useGenerate(load, () => setTitle(''))

  useEffect(load, [load])

  function reload() {
    setLoadState('loading')
    load()
  }

  // 저장 뒤에는 서버가 정한 순서와 기한 초과를 그대로 쓴다. 다시 불러오지 못하면 받은 응답만 반영한다.
  async function refreshOrApply(fallback: (prev: Task[]) => Task[]) {
    try {
      setTasks(await listTasks())
    } catch {
      setTasks(fallback)
    }
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
      // 설명·마감일·우선순위를 채운 때만 한 번 더 저장한다. 비워 두면 예전과 똑같이 제목만 만든다.
      const hasExtras = description.trim() !== '' || dueDate !== '' || priority !== 'NORMAL'
      let saved = created
      let extrasFailed = false
      if (hasExtras) {
        try {
          saved = await updateTask(created.id, {
            title: created.title,
            description: description || null,
            due_date: dueDate || null,
            priority,
          })
        } catch {
          extrasFailed = true
        }
      }
      await refreshOrApply((prev) => [...prev, saved])
      setTitle('')
      setDescription('')
      setDueDate('')
      setPriority('NORMAL')
      suggest.reset()
      setAlert(extrasFailed ? EXTRA_ERROR : '')
    } catch {
      setAlert(SAVE_ERROR)
    } finally {
      setCreating(false)
    }
  }

  // 제목(주제)과 설명 입력칸의 내용을 그대로 보낸다.
  function handleGenerate() {
    if (!title.trim()) {
      setTitleError('제목을 입력해 주세요.')
      return
    }
    gen.run(title.trim(), description)
  }

  function handleSuggest() {
    if (!title.trim()) {
      setTitleError('제목을 입력해 주세요.')
      return
    }
    suggest.run(title.trim(), description)
  }

  async function handleStatus(task: Task, status: Status) {
    setBusyIds((prev) => [...prev, task.id])
    try {
      const updated = await updateTask(task.id, { status })
      await refreshOrApply((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
      setAlert('')
    } catch {
      setAlert(SAVE_ERROR)
    } finally {
      setBusyIds((prev) => prev.filter((id) => id !== task.id))
    }
  }

  async function handleDelete(task: Task) {
    if (!window.confirm(`"${task.title}" 카드를 삭제할까요? 되돌릴 수 없습니다.`)) return
    setBusyIds((prev) => [...prev, task.id])
    try {
      await deleteTask(task.id)
      setTasks((prev) => prev.filter((t) => t.id !== task.id))
      setAlert('')
    } catch {
      setAlert(DELETE_ERROR)
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
      <article className={`card${t.is_overdue ? ' overdue' : ''}`} key={t.id} onClick={() => setEditingId(t.id)}>
        <h3>{t.title}</h3>
        <span className={`priority ${t.priority}`}>{PRIORITY_LABEL[t.priority]}</span>
        {t.is_overdue && <span className="badge-overdue">기한 초과</span>}
        {t.due_date && <p className="due">{t.due_date}</p>}
        <div className="card-actions" onClick={(e) => e.stopPropagation()}>
          <select
            value={t.status}
            disabled={busyIds.includes(t.id)}
            onChange={(e) => handleStatus(t, e.target.value as Status)}
            aria-label={`${t.title}: 진행 상태`}
          >
            {COLUMNS.map((c) => (
              <option key={c.status} value={c.status}>
                {c.label}
              </option>
            ))}
          </select>
          <button disabled={busyIds.includes(t.id)} onClick={() => setEditingId(t.id)} aria-label={`${t.title}: 수정`}>
            수정
          </button>
          <button
            className="danger"
            disabled={busyIds.includes(t.id)}
            onClick={() => handleDelete(t)}
            aria-label={`${t.title}: 삭제`}
          >
            삭제
          </button>
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
          <div className="create-extra">
            <textarea
              rows={2}
              value={description}
              maxLength={1000}
              placeholder="설명 (선택)"
              onChange={(e) => setDescription(e.target.value)}
            />
            <div className="extra-row">
              <button type="button" disabled={suggest.suggesting} onClick={handleSuggest}>
                AI 제안
              </button>
              <button type="button" disabled={gen.generating || gen.registering} onClick={handleGenerate}>
                AI로 할 일 만들기
              </button>
              {suggest.suggesting && <span className="suggest-note">제안을 받는 중...</span>}
              {gen.generating && <span className="suggest-note">할 일을 만드는 중...</span>}
              <label className="inline">
                마감일
                <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </label>
              {PRIORITIES.map((p) => (
                <label key={p.value} className="inline">
                  <input
                    type="radio"
                    name="create-priority"
                    checked={priority === p.value}
                    onChange={() => setPriority(p.value)}
                  />
                  {p.label}
                </label>
              ))}
            </div>
            {suggest.reason && <p className="suggest-note">AI 제안 이유: {suggest.reason}</p>}
            {suggest.error && <p className="field-error">{suggest.error}</p>}
            {gen.reason && <p className="suggest-note">AI 안내: {gen.reason}</p>}
            {gen.error && <p className="field-error">{gen.error}</p>}
            {gen.candidates.length > 0 && <GeneratePanel gen={gen} />}
          </div>
        </form>
        <div className="user">
          <span>{user.email}</span>
          <button onClick={onLogout}>로그아웃</button>
        </div>
      </header>
      {alert && (
        <div className="alert" role="alert">
          <span>⚠ {alert}</span>
          <button onClick={() => setAlert('')}>닫기</button>
        </div>
      )}
      <BriefingCard tasks={tasks} />
      <CommandPanel tasks={tasks} onTasksChange={setTasks} disabled={loadState !== 'ready'} />
      <WeekPlanCard tasks={tasks} />
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
            refreshOrApply((prev) => prev.map((t) => (t.id === saved.id ? saved : t)))
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

const LOGIN_PATH = '/login'

type AuthState = { phase: 'checking' } | { phase: 'out' } | { phase: 'in'; user: User }

function App() {
  const [auth, setAuth] = useState<AuthState>({ phase: 'checking' })

  const goLogin = useCallback(() => {
    if (window.location.pathname !== LOGIN_PATH) window.history.replaceState(null, '', LOGIN_PATH)
    setAuth({ phase: 'out' })
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(goLogin)
    getMe()
      .then((user) => {
        if (window.location.pathname === LOGIN_PATH) window.history.replaceState(null, '', '/')
        setAuth({ phase: 'in', user })
      })
      .catch(goLogin) // 401이면 로그인 화면으로 이동한다
  }, [goLogin])

  if (auth.phase === 'checking') return <p className="auth-note">확인하는 중…</p>
  if (auth.phase === 'out') {
    return (
      <Login
        onDone={(user) => {
          window.history.replaceState(null, '', '/')
          setAuth({ phase: 'in', user })
        }}
      />
    )
  }
  return (
    <Board
      key={auth.user.id}
      user={auth.user}
      onLogout={() => {
        logout().finally(goLogin)
      }}
    />
  )
}

export default App
