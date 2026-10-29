import { useState } from 'react'
import { ApiError, getWeekPlan } from './api'
import type { WeekPlan } from './api'

const WEEKPLAN_OFF = '지금은 계획을 쓸 수 없습니다'
const WEEKPLAN_FAILED = '계획을 받지 못했습니다'

// [이번 주 계획] 버튼의 요청 상태. 받은 계획은 닫을 때까지 보여 준다.
export function useWeekPlan() {
  const [loading, setLoading] = useState(false)
  const [plan, setPlan] = useState<WeekPlan | null>(null)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    close()
    try {
      setPlan(await getWeekPlan())
    } catch (e) {
      setError(e instanceof ApiError && e.status === 502 ? WEEKPLAN_FAILED : WEEKPLAN_OFF)
    } finally {
      setLoading(false)
    }
  }

  function close() {
    setPlan(null)
    setError('')
  }

  return { loading, plan, error, run, close }
}
