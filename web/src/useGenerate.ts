import { useState } from 'react'
import { ApiError, createTask, generateTasks, updateTask } from './api'
import type { GeneratedTask } from './api'

const GENERATE_OFF = '지금은 AI를 쓸 수 없습니다. 직접 입력해 주세요.'
const GENERATE_FAILED = '할 일을 못 만들었습니다. 다시 눌러 보세요.'

// [AI로 할 일 만들기] 버튼의 상태. 주제와 설명은 호출하는 쪽의 제목·설명 입력칸 값을 그대로 받는다.
export function useGenerate(onRegistered: () => void, onAllDone: () => void) {
  const [generating, setGenerating] = useState(false)
  const [registering, setRegistering] = useState(false)
  const [candidates, setCandidates] = useState<GeneratedTask[]>([])
  const [checked, setChecked] = useState<boolean[]>([])
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')

  function show(tasks: GeneratedTask[]) {
    setCandidates(tasks)
    setChecked(tasks.map(() => true))
  }

  function reset() {
    show([])
    setError('')
    setReason('')
  }

  async function run(topic: string, description: string) {
    setGenerating(true)
    reset()
    try {
      const res = await generateTasks(topic, description)
      show(res.tasks)
      setReason(res.reason)
    } catch (e) {
      setError(e instanceof ApiError && e.status === 502 ? GENERATE_FAILED : GENERATE_OFF)
    } finally {
      setGenerating(false)
    }
  }

  function toggle(index: number, value: boolean) {
    setChecked((prev) => prev.map((v, i) => (i === index ? value : v)))
  }

  // 고른 후보만 기존 방식(만들기 -> 필요하면 수정)으로 하나씩 등록한다.
  async function register() {
    const picked = candidates.filter((_, i) => checked[i])
    if (picked.length === 0) return
    setRegistering(true)
    setError('')
    const failed: GeneratedTask[] = []
    for (const c of picked) {
      try {
        const created = await createTask(c.title)
        if (c.description || c.due_date || c.priority !== 'NORMAL') {
          try {
            await updateTask(created.id, {
              title: created.title,
              description: c.description || null,
              due_date: c.due_date,
              priority: c.priority,
            })
          } catch {
            // 제목만 저장된 카드로 남는다. 카드를 눌러 고칠 수 있다.
          }
        }
      } catch {
        failed.push(c)
      }
    }
    onRegistered()
    if (failed.length === 0) {
      reset()
      onAllDone()
    } else {
      show(failed)
      setError(`${failed.length}개를 등록하지 못했습니다. 다시 시도해 주세요.`)
    }
    setRegistering(false)
  }

  return { generating, registering, candidates, checked, error, reason, run, toggle, register, reset }
}
