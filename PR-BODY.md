## 개요
사용자별 Task 분리 (가입·로그인·로그아웃·현재 사용자, 모든 Task API 보호). 병합되면 #6 이 닫힌다. Close #6

## 변경 내용
- 가입, 로그인, 로그아웃, 현재 사용자 API와 로그인 화면(미로그인 시 `/login` 이동). 비밀번호는 scrypt 해시, 세션은 HttpOnly 쿠키이며 DB에는 토큰 해시만 둔다.
- 모든 Task API에 로그인 요구, `tasks.owner_id` 추가와 기존 데이터 이전(alembic `0002`, `--autogenerate` 없이 직접 작성).

## 확인한 것 — 데이터
| 항목 | 이전 전 | 이전 후 (복사본 DB) |
|---|---|---|
| tasks 수 | 1 | 1 |
| owner_id 가 빈 Task | - | 0 |
| users | - | `owner@taskflow.local` (비밀번호 없음) |

`upgrade head` → `downgrade 0001` → `upgrade head` 도 복사본에서 통과. 실제 `tasks.db` 에는 upgrade 를 하지 않았다(작성자가 백업 후 실행).

## 확인한 것 — 분리 · 회귀 (`uv run python -m unittest discover -s tests`, 6개 통과)
- A 가 B 의 Task 수정(제목·상태) → 404, 삭제 → 404, B 의 Task 는 그대로
- 로그아웃 뒤 목록 → 401, 로그인 없이 네 Task 요청 → 401
- 로그인 뒤 시나리오(생성 → 수정 → 상태 변경 → 삭제) 통과
- 응답에 비밀번호·해시·토큰 없음, DB 에 평문 비밀번호·토큰 없음
- `npm run build`, `npm run lint` 통과

## 확인하지 못한 것
- 브라우저에서 `/login` 이동을 직접 눈으로 보지는 못했다(코드와 빌드까지만 확인).
