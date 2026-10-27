import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { deleteTask, updateTask } from './api'
import type { Priority, Task } from './api'

const PRIORITIES: { value: Priority; label: string }[] = [
  { value: 'HIGH', label: '높음' },
  { value: 'NORMAL', label: '보통' },
  { value: 'LOW', label: '낮음' },
]

interface Props {
  task: Task
  onClose: () => void
  onSaved: (task: Task) => void
  onDeleted: (id: number) => void
}

function EditModal({ task, onClose, onSaved, onDeleted }: Props) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description ?? '')
  const [dueDate, setDueDate] = useState(task.due_date ?? '')
  const [priority, setPriority] = useState<Priority>(task.priority)
  const [titleError, setTitleError] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) {
      setTitleError('제목을 입력해 주세요.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const saved = await updateTask(task.id, {
        title: title.trim(),
        description: description || null,
        due_date: dueDate || null,
        priority,
      })
      onSaved(saved)
    } catch {
      setError('저장하지 못했습니다. 다시 시도해 주세요.')
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`"${task.title}" 카드를 삭제할까요? 되돌릴 수 없습니다.`)) return
    setBusy(true)
    setError('')
    try {
      await deleteTask(task.id)
      onDeleted(task.id)
    } catch {
      setError('삭제하지 못했습니다. 다시 시도해 주세요.')
      setBusy(false)
    }
  }

  return (
    <div className="backdrop" onClick={onClose}>
      <form
        className="modal"
        role="dialog"
        aria-label="Task 수정"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSave}
      >
        <h2>Task 수정</h2>
        <label>
          제목
          <input
            autoFocus
            value={title}
            maxLength={100}
            onChange={(e) => {
              setTitle(e.target.value)
              setTitleError('')
            }}
          />
        </label>
        {titleError && <p className="field-error">{titleError}</p>}
        <label>
          설명
          <textarea
            rows={3}
            value={description}
            maxLength={1000}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label>
          마감일
          <span className="row">
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            <button type="button" onClick={() => setDueDate('')}>
              날짜 지우기
            </button>
          </span>
        </label>
        <fieldset>
          <legend>우선순위</legend>
          {PRIORITIES.map((p) => (
            <label key={p.value} className="inline">
              <input
                type="radio"
                name="priority"
                checked={priority === p.value}
                onChange={() => setPriority(p.value)}
              />
              {p.label}
            </label>
          ))}
        </fieldset>
        {error && <p className="field-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="danger" disabled={busy} onClick={handleDelete}>
            삭제
          </button>
          <span className="spacer" />
          <button type="button" onClick={onClose}>
            취소
          </button>
          <button type="submit" disabled={busy}>
            저장
          </button>
        </div>
      </form>
    </div>
  )
}

export default EditModal
