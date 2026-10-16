# AGENTS.md

## 프로젝트
- `app.py`: 파이썬 표준 라이브러리만 쓰는 터미널용 간단 게시판
- 데이터는 현재 폴더의 `board.json`에 저장한다

## 규칙
- 외부 패키지를 추가하지 않는다
- 요청받은 파일만 수정한다
- 기존 명령(`add`, `list`, `show`, `delete`)의 출력 형식을 바꾸지 않는다
- 커밋 메시지는 `feat:`, `fix:`, `docs:`, `chore:` 접두어를 쓴다

## 실행
```bash
python3 app.py add "제목" "내용" --author 이름
python3 app.py list
python3 app.py show 1
python3 app.py delete 1
```
