# DEV-ENVIRONMENT

개발 환경 기록. 확인일: 2026-10-19

## 운영체제 · 셸
| 항목 | 값 |
|---|---|
| 운영체제 | Ubuntu 24.04.5 LTS (WSL2) |
| 커널 | Linux 6.18.40.1-microsoft-standard-WSL2 x86_64 |
| 셸 | /bin/bash, GNU bash 5.2.21(1)-release |

## 도구별 버전 (`--version` 결과 그대로)
| 도구 | 명령 | 결과 |
|---|---|---|
| git | `git --version` | `git version 2.43.0` |
| node | `node --version` | `v24.22.0` |
| npm | `npm --version` | `11.19.1` |
| uv | `uv --version` | `uv 0.13.1 (x86_64-unknown-linux-gnu)` |
| python | `python3 --version` | `Python 3.12.3` (시스템) |
| python | `uv run --project api python --version` | `Python 3.12.15` (uv 관리, `api/` 프로젝트가 쓰는 것) |

- 시스템에는 `python`, `pip`, `pip3`, `pipx`, `sqlite3` 명령이 없다. 시스템 Python에는 `ensurepip`도 없어서 `python3 -m venv`는 쓸 수 없다. 가상환경과 패키지는 uv로 관리한다.
- SQLite는 Python에 내장된 라이브러리(3.45.1)를 쓴다.

## 새로 설치한 것
시스템 수준 설치는 없다. 아래는 모두 프로젝트 폴더 안에만 설치했다.

### `api/` (uv 프로젝트, `uv add "fastapi[standard]"`)
- 직접 요청한 패키지: `fastapi[standard]` (`pyproject.toml`에는 `>=0.146.0`으로 기록됨)
- 설치된 주요 버전: fastapi 0.146.0, uvicorn 0.54.0
- 의존 패키지는 `[standard]`가 함께 가져온 것이며 `api/uv.lock`에 고정되어 있다.
- 가상환경: `api/.venv`

### `web/` (`npm create vite@latest web -- --template react-ts` 후 `npm install`)
| 패키지 | 설치된 버전 |
|---|---|
| react | 19.3.1 |
| react-dom | 19.3.1 |
| vite | 8.3.4 |
| @vitejs/plugin-react | 6.1.2 |
| typescript | 6.0.3 |
| oxlint | 1.88.0 |
| @types/react | 19.3.0 |
| @types/react-dom | 19.3.0 |
| @types/node | 24.19.2 |

- 템플릿 버전: create-vite 9.2.1
- Vite 요구 Node 버전은 `^20.19.0 || >=22.12.0`이고 현재 Node는 이를 충족한다.
- 잠금 파일: `web/package-lock.json`

## 실행
```bash
# API
cd api && uv run fastapi dev

# 화면
cd web && npm run dev
```
2026-10-19 M0 검증: API `GET /health` 200(CORS 헤더 확인), 화면 `npm run build`·`npm run lint` 통과, Vite 개발 서버 기동 확인. SQLite 파일은 생성되지 않음.
