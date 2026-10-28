import { useState } from 'react'
import { ApiError, suggestTask } from './api'
import type { Suggestion } from './api'

const SUGGEST_OFF = '지금은 AI 제안을 쓸 수 없습니다. 직접 입력해 주세요.'
const SUGGEST_FAILED = '제안을 못 받았습니다. 다시 제안 버튼을 눌러 보세요.'

// [AI 제안] 버튼의 요청 상태. 성공하면 apply로 칸만 채우고, 저장은 하지 않는다.
export function useSuggest(apply: (s: Suggestion) => void) {
  const [suggesting, setSuggesting] = useState(false)
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')

  async function run(title: string, description: string) {
    setSuggesting(true)
    setError('')
    setReason('')
    try {
      const s = await suggestTask(title, description)
      apply(s)
      setReason(s.reason)
    } catch (e) {
      setError(e instanceof ApiError && e.status === 502 ? SUGGEST_FAILED : SUGGEST_OFF)
    } finally {
      setSuggesting(false)
    }
  }

  function reset() {
    setError('')
    setReason('')
  }

  return { suggesting, error, reason, run, reset }
}
