import type { Task } from './api'
import './WeekPlanCard.css'
import { useWeekPlan } from './useWeekPlan'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

// YYYY-MM-DD를 '10/29 (목)'으로. 시간대에 따라 하루 밀리지 않게 직접 쪼갠다.
function dayLabel(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return `${m}/${d} (${WEEKDAYS[new Date(y, m - 1, d).getDay()]})`
}

// 보드 위의 [이번 주 계획] 버튼과 요일별 표. 제목은 지금 보드에 있는 카드에서 id로 찾는다.
function WeekPlanCard({ tasks }: { tasks: Task[] }) {
  const { loading, plan, error, run, close } = useWeekPlan()
  const titles = new Map(tasks.map((t) => [t.id, t.title]))

  return (
    <section className="weekplan">
      <button type="button" disabled={loading} onClick={run}>
        {loading ? '만드는 중…' : '이번 주 계획'}
      </button>
      {error && <p className="field-error">{error}</p>}
      {plan && (
        <div className="weekplan-card" role="region" aria-label="이번 주 계획">
          <table>
            <thead>
              <tr>
                <th scope="col">날짜</th>
                <th scope="col">할 일</th>
              </tr>
            </thead>
            <tbody>
              {plan.days.map((day, i) => {
                const names = day.ids.filter((id) => titles.has(id)).map((id) => titles.get(id))
                return (
                  <tr key={day.date} className={i === 0 ? 'today' : undefined}>
                    <th scope="row">{i === 0 ? `${dayLabel(day.date)} 오늘` : dayLabel(day.date)}</th>
                    <td>
                      {names.length === 0 ? (
                        <span className="rest">—</span>
                      ) : (
                        <ul>
                          {names.map((name, j) => (
                            <li key={j}>{name}</li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="note">{plan.note}</p>
          <button type="button" onClick={close}>
            닫기
          </button>
        </div>
      )}
    </section>
  )
}

export default WeekPlanCard
