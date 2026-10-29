import { useState } from 'react'
import { ApiError, getBriefing } from './api'
import type { Briefing } from './api'

const BRIEFING_OFF = '지금은 브리핑을 쓸 수 없습니다'
const BRIEFING_FAILED = '브리핑을 받지 못했습니다'

// [오늘 브리핑] 버튼의 요청 상태. 받은 브리핑은 닫을 때까지 보여 준다.
export function useBriefing() {
  const [loading, setLoading] = useState(false)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    close()
    try {
      setBriefing(await getBriefing())
    } catch (e) {
      setError(e instanceof ApiError && e.status === 502 ? BRIEFING_FAILED : BRIEFING_OFF)
    } finally {
      setLoading(false)
    }
  }

  function close() {
    setBriefing(null)
    setError('')
  }

  return { loading, briefing, error, run, close }
}
