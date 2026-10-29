import type { Task } from './api'
import './BriefingCard.css'
import { useBriefing } from './useBriefing'

const MARKS = ['①', '②', '③']

// 보드 위의 [오늘 브리핑] 버튼과 결과 카드. 제목은 지금 보드에 있는 카드에서 id로 찾는다.
function BriefingCard({ tasks }: { tasks: Task[] }) {
  const { loading, briefing, error, run, close } = useBriefing()
  const titles = new Map(tasks.map((t) => [t.id, t.title]))
  const top = briefing?.top3.filter((t) => titles.has(t.id)) ?? []
  const later = briefing?.later.filter((id) => titles.has(id)) ?? []

  return (
    <section className="briefing">
      <button type="button" disabled={loading} onClick={run}>
        {loading ? '만드는 중…' : '오늘 브리핑'}
      </button>
      {error && <p className="field-error">{error}</p>}
      {briefing && (
        <div className="briefing-card" role="region" aria-label="오늘 브리핑">
          {top.length > 0 && (
            <>
              <h2>먼저 할 일</h2>
              <ol>
                {top.map((t, i) => (
                  <li key={t.id}>
                    <span className="mark">{MARKS[i]}</span>
                    <span>
                      <strong>{titles.get(t.id)}</strong>
                      {t.reason && ` — ${t.reason}`}
                    </span>
                  </li>
                ))}
              </ol>
            </>
          )}
          {later.length > 0 && (
            <>
              <h2>미뤄도 되는 일</h2>
              <ul>
                {later.map((id) => (
                  <li key={id}>{titles.get(id)}</li>
                ))}
              </ul>
            </>
          )}
          <p className="cheer">{briefing.cheer}</p>
          <button type="button" onClick={close}>
            닫기
          </button>
        </div>
      )}
    </section>
  )
}

export default BriefingCard
