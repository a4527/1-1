# DATA-MIGRATION-PLAN (M2 로그인)

`tasks`에 주인을 붙이고 기존 Task를 잃지 않는 순서다. 도구는 alembic(`api/migrations`)이다. `--autogenerate`는 쓰지 않고 이전 절차를 직접 썼다. 별도 이전 스크립트는 없다.

## 1. 바뀌는 것
| 대상 | 변경 |
|---|---|
| `users` (새 표) | `id`, `email`(유일), `password_hash`(비어 있을 수 있음), `created_at` |
| `sessions` (새 표) | `token_hash`(기본키, SHA-256), `user_id`(→users, 삭제 시 함께 삭제), `created_at`, `expires_at` |
| `tasks` | `owner_id INTEGER NOT NULL REFERENCES users(id)` 추가, 인덱스 `ix_tasks_owner_id` |

## 2. 순서 (revision `0002`)
0. `0001`은 기준선이다. 이미 `tasks`가 있는 DB에서는 아무것도 하지 않는다.
1. `users`, `sessions`를 만든다.
2. 기존 Task가 하나라도 있으면 주인 계정 하나를 비밀번호 없이 만든다(`owner@taskflow.local`, `TASKFLOW_LEGACY_OWNER_EMAIL`로 변경 가능). (D-010)
3. `owner_id NOT NULL`이 있는 `tasks_new`를 만들고 모든 행을 같은 `id`로 옮기며 주인을 붙인다. 기존 `CHECK` 규칙은 그대로 둔다.
4. `tasks_new`의 행 수가 옛 `tasks`와 다르면 오류로 멈춘다(옛 표는 그대로). 같으면 옛 표를 지우고 이름을 `tasks`로 바꾸고, 삭제된 번호를 다시 쓰지 않도록 번호 기록(`sqlite_sequence`)을 이어 준다.
5. `downgrade`는 `owner_id`를 뺀 표로 되돌린다. Task는 남고 계정·세션은 사라진다.

## 3. 실제 DB에 적용하기 (사람이 한다)
```bash
cd api
cp tasks.db tasks.db.bak-$(date +%Y%m%d-%H%M%S)   # 1. 백업
uv run alembic upgrade head                         # 2. 적용
uv run alembic current                              # 3. 0002 (head) 인지 확인
```
- 적용 전후에 같은 질문으로 숫자를 비교한다: `SELECT count(*) FROM tasks`, `SELECT count(*) FROM tasks WHERE owner_id IS NULL`(0이어야 함), `SELECT email FROM users`.
- 되돌릴 때는 백업 파일을 `tasks.db`로 되돌려 놓는다.

## 4. 이전 전 수량 (읽기 전용으로 확인, 2026-10-23)
| 항목 | 값 |
|---|---|
| DB 파일 | `api/tasks.db` (`TASKFLOW_DB`로 바꿀 수 있음, Git 제외) |
| tasks 전체 | 1 |
| 상태별 | done 1 |
| 표본 | id 1 · `테스트1` · 설명 없음 · done |

복사본에 `upgrade head` → `downgrade 0001` → `upgrade head`를 해 본 결과: Task 1 → 1, `owner_id`가 빈 Task 0, 계정 `owner@taskflow.local`(비밀번호 없음), 번호 기록 유지. 실제 DB 파일은 건드리지 않았다(전후 md5 동일).

## 5. 정하지 않은 것
- 여러 사람이 쓰는 배포 환경에서 주인 계정을 넘겨받는 방식(D-010 재검토).
