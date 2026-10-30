# 나중에 고칠 것 (REFACTOR-LATER)

리뷰에서 나왔지만 지금 PR에서는 고치지 않기로 한 항목이다. 고칠 때 이 표에서 지우고 PR 번호를 커밋에 적는다.

| # | 발견 | 위치 | 내용 | 왜 나중인가 | 고칠 때 |
|---|---|---|---|---|---|
| L-001 | #17 리뷰 | `api/src/api/briefing.py` · `api/src/api/weekplan.py` | 끝나지 않은 할 일 모으기(조회·30개 자르기·`id·title·priority·due_date·overdue`로 바꾸기)와 id 검사가 두 파일에 그대로 중복된다. 두 파일 모두 `suggest.py`의 비공개 함수(`_call_model` 등)를 가져다 쓴다. | 기존 AI 기능 코드는 이번 PR에서 바꾸지 않는다. 세 번째 AI 기능이 생기면 공통 모양이 확실해진다. | `ai_common.py`(가칭)에 `open_tasks()` · `task_items()` · `known_id()`를 모으고 공개 이름으로 바꾼다. 필드를 하나 더할 때 두 곳을 고쳐야 하면 그때 바로 한다. |
| L-002 | #17 리뷰 | `web/src/useBriefing.tsx` · `web/src/useWeekPlan.tsx`, `BriefingCard.css` · `WeekPlanCard.css` | 요청 훅과 카드 껍데기 CSS가 이름과 문구만 다른 복사본이다. | 새 파일로만 만든다는 범위를 지킨다. | 제네릭 훅(`useAiRequest`)과 공통 `.ai-card` 클래스로 합친다. |
| L-003 | #17 리뷰 | `briefing.py` · `weekplan.py` `MAX_TASKS` | 끝나지 않은 할 일이 31개를 넘으면 뒤쪽은 말없이 빠진다. | 지금 사용 규모에서는 드물다. | 응답에 빠진 개수를 넣고 화면에 알린다. |
