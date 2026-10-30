import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, commandTasks, createTask, listTasks, updateTask } from './api'
import type { Task } from './api'
import type { CommandAction } from './types'

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.status === 422) return error.message
    if (error.status === 503) return '지금은 시킬 수 없습니다'
    if (error.status === 502) return '알아듣지 못했습니다'
  }
  return fallback
}

function describe(action: CommandAction, tasks: Task[]) {
  if (action.kind === 'add') return `${action.title} — 추가`
  const task = tasks.find((item) => item.id === action.id)
  const title = task?.title ?? '찾을 수 없는 할 일'
  if (action.kind === 'done') return `${title}(지금 마감: ${task?.due_date ?? '없음'}) — 완료로`
  return `${title}(지금 마감: ${task?.due_date ?? '없음'}) — ${action.value ? `마감을 ${action.value}로` : '마감 없음으로'}`
}

export default function CommandPanel({ tasks, onTasksChange, disabled }: {
  tasks: Task[]
  onTasksChange: (tasks: Task[]) => void
  disabled: boolean
}) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [actions, setActions] = useState<CommandAction[]>([])
  const [ask, setAsk] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState<number[]>([])
  const [saving, setSaving] = useState<number | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({})
  const [refreshError, setRefreshError] = useState(false)
  const busy = useRef(false)
  const applied = useRef(new Set<number>())

  async function refresh() {
    try {
      onTasksChange(await listTasks())
      setRefreshError(false)
    } catch {
      setRefreshError(true)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy.current || disabled || refreshError) return
    if (!text.trim()) {
      setError('문장을 입력해 주세요.')
      return
    }
    busy.current = true
    setLoading(true)
    setError('')
    setActions([])
    setAsk(null)
    setSaved([])
    applied.current.clear()
    setRowErrors({})
    try {
      const result = await commandTasks(text.trim())
      if (result.ask) setAsk(result.ask)
      else setActions(result.actions)
    } catch (err) {
      setError(errorMessage(err, '요청하지 못했습니다. 다시 시도해 주세요.'))
    } finally {
      busy.current = false
      setLoading(false)
    }
  }

  async function apply(action: CommandAction, index: number) {
    if (busy.current || disabled || refreshError || applied.current.has(index)) return
    const target = action.kind === 'add' ? undefined : tasks.find((task) => task.id === action.id)
    if (action.kind !== 'add' && (!target || target.status === 'done')) {
      setRowErrors((prev) => ({ ...prev, [index]: '적용할 수 없는 할 일입니다. 새 문장으로 다시 시켜 주세요.' }))
      return
    }
    busy.current = true
    setSaving(index)
    setRowErrors((prev) => ({ ...prev, [index]: '' }))
    try {
      if (action.kind === 'add') await createTask(action.title)
      else if (action.kind === 'due') await updateTask(action.id, { due_date: action.value })
      else await updateTask(action.id, { status: 'done' })
      // 저장 성공을 조회보다 먼저 기억해서 목록 조회 실패 시 중복 등록을 막는다.
      applied.current.add(index)
      setSaved((prev) => [...prev, index])
      await refresh()
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [index]: errorMessage(err, '적용하지 못했습니다. 다시 시도해 주세요.') }))
    } finally {
      busy.current = false
      setSaving(null)
    }
  }

  async function retryRefresh() {
    if (busy.current) return
    busy.current = true
    setLoading(true)
    try {
      await refresh()
    } finally {
      busy.current = false
      setLoading(false)
    }
  }

  const locked = disabled || loading || saving !== null || refreshError
  return (
    <section className="briefing" aria-label="한 문장으로 시키기" aria-busy={loading || saving !== null}>
      <form onSubmit={submit} style={{ display: 'flex', gap: 8, width: '100%', maxWidth: 720 }}>
        <input
          aria-label="시킬 문장"
          placeholder="예: 보고서 마감을 내일로 바꿔 줘"
          value={text}
          maxLength={200}
          disabled={locked}
          onChange={(event) => setText(event.target.value)}
          style={{ flex: 1, minWidth: 0, padding: 8 }}
        />
        <button type="submit" disabled={locked || !text.trim()}>
          {loading ? '알아듣는 중.....' : '시키기'}
        </button>
      </form>
      {error && <p className="field-error" role="alert" style={{ whiteSpace: 'pre-line' }}>{error}</p>}
      {ask && <p role="status" style={{ margin: 0 }}>{ask}</p>}
      {actions.length > 0 && (
        <div className="briefing-card" role="region" aria-label="명령 확인">
          <h2>이렇게 바꿀까요? {actions.length}개</h2>
          <ol>
            {actions.map((action, index) => (
              <li key={index} style={{ flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ flex: '1 1 180px' }}>{describe(action, tasks)}</span>
                <button type="button" disabled={locked || saved.includes(index)} onClick={() => apply(action, index)}>
                  {saved.includes(index) ? '적용됨' : saving === index ? '적용 중…' : '적용'}
                </button>
                {rowErrors[index] && <p className="field-error" role="alert">{rowErrors[index]}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}
      {refreshError && (
        <div role="alert">
          <p className="field-error">적용했습니다. 목록을 다시 불러오지 못했습니다.</p>
          <button type="button" disabled={loading} onClick={retryRefresh}>목록 다시 불러오기</button>
        </div>
      )}
    </section>
  )
}
