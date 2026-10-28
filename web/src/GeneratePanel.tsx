import { PRIORITIES } from './api'
import type { useGenerate } from './useGenerate'

const PRIORITY_LABEL = Object.fromEntries(PRIORITIES.map((p) => [p.value, p.label]))

// 만들어진 후보 목록. 체크한 것만 등록한다.
function GeneratePanel({ gen }: { gen: ReturnType<typeof useGenerate> }) {
  const count = gen.checked.filter(Boolean).length
  return (
    <div className="generate-panel" role="group" aria-label="AI가 만든 할 일">
      <ul className="candidates">
        {gen.candidates.map((c, i) => (
          <li key={i}>
            <label>
              <input
                type="checkbox"
                checked={gen.checked[i] ?? false}
                disabled={gen.registering}
                onChange={(e) => gen.toggle(i, e.target.checked)}
              />
              <span>
                <strong>{c.title}</strong>
                <span className="suggest-note">
                  {' '}
                  {PRIORITY_LABEL[c.priority]}
                  {c.due_date && ` · ${c.due_date}`}
                </span>
                {c.description && <span className="suggest-note block">{c.description}</span>}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <div className="generate-row">
        <button type="button" disabled={gen.registering || count === 0} onClick={gen.register}>
          {gen.registering ? '등록 중...' : `선택한 ${count}개 등록`}
        </button>
        <button type="button" disabled={gen.registering} onClick={gen.reset}>
          닫기
        </button>
      </div>
    </div>
  )
}

export default GeneratePanel
