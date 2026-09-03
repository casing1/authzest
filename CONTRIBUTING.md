# Contributing

AuthGuard(가칭)에 기여해 주셔서 감사합니다.

## 개발 환경

1. Python 3.12 가상 환경을 만듭니다.
2. `python -m pip install -e '.[dev]'`로 Python 개발 의존성을 설치합니다.
3. `frontend/`에서 `npm install`을 실행합니다.
4. 변경 전후에 아래 검증을 실행합니다.

```bash
pytest
ruff check .
ruff format --check .
cd frontend && npm run lint && npm run format:check && npm run build
```

독립 실행 파일을 확인하려면 프론트엔드를 빌드한 뒤 아래 명령을 실행합니다.

```bash
python -m pip install -e '.[build]'
python -m PyInstaller --clean --noconfirm authguard.spec
./dist/authguard doctor
```

## 변경 원칙

- `analyzer`, `parser`, `codex`, `runner` 경계를 유지합니다.
- core가 CLI, FastAPI transport, React UI에 의존하지 않게 합니다.
- 보안 finding을 추가할 때는 재현 가능한 최소 테스트를 포함합니다.
- 실제 Codex 연동은 `CodexAdapter` protocol 구현체로 추가하고, core에 SDK/프로세스 세부사항을
  노출하지 않습니다.
- 커밋과 pull request는 한 가지 목적에 집중하고 사용자에게 보이는 변경을 문서화합니다.

버그와 기능 제안은 재현 절차, 기대 결과, 실제 결과, 실행 환경을 포함해 issue로 남겨 주세요.
보안 취약점은 공개 issue 대신 [SECURITY.md](SECURITY.md)의 절차를 따라 주세요.
