# FastAPI 라우트 탐색

[문서](INDEX.ko.md) · [English](../PARSER_SCOPE.md) · 한국어

이 문서는 현재 `main`의 소스를 설명합니다. FastAPI 객체 식별, prefix 합성, 저장소 내부 import 해석은
[`Unreleased`](CHANGELOG.ko.md#unreleased) 변경이며 배포된
[v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)에 포함되어 있지 않습니다.
이 기능을 사용하려면 현재 소스를 checkout하세요. 패키지 버전은 아직 `0.1.0a1`에서 올리지 않았습니다.

AuthZest는 Python 표준 라이브러리의 AST 파서로 Python 소스를 분석합니다. 분석 대상 애플리케이션을
import하거나 객체를 생성하거나 코드를 실행하지 않습니다. 지원 문법은 Python 3.12에서 테스트합니다.

## 지원하는 선언

라우트는 식별 가능한 FastAPI import로부터 직접 생성한 객체에 속해야 합니다. 단일 파일 탐색은 그 파일의
선언을 식별하며, 저장소 스캔은 색인에 포함된 소스 파일 사이의 지원되는 import도 연결합니다.

```python
from fastapi import FastAPI, APIRouter as Router

app = FastAPI()
router = Router()


@app.get("/health")
def health():
    return {"status": "ok"}


@router.post("/users")
async def create_user():
    pass
```

`import fastapi`, `import fastapi as fa`, `router: Router = Router()`와 같은 타입 주석이 있는 대입도
지원합니다. 타입 주석만으로는 객체가 생성된 것으로 보지 않습니다.

지원하는 데코레이터는 소문자 `get`, `post`, `put`, `patch`, `delete`, `options`, `head`입니다. 정확히 하나의
위치 인자로 문자열 리터럴을 받아야 합니다. `path=` 키워드나 `**kwargs` 전개가 있으면 해당 선언을 해석하지
않습니다. 동기·비동기 함수와 한 함수에 붙은 여러 개의 지원되는 데코레이터를 모두 수집합니다. 각 라우트는
HTTP 메서드, 함수 이름, 파일, 1부터 시작하는 함수 정의의 줄 번호를 유지합니다.

함수 안에서 순서대로 객체를 직접 만드는 패턴도 지원합니다. 다음과 같은 애플리케이션 팩토리가 해당합니다.

```python
from fastapi import FastAPI


def create_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
```

탐색 결과는 소스의 선언을 설명합니다. 팩토리가 실제로 호출되거나 라우터가 실행 중인 애플리케이션에
등록되었다는 증거는 아닙니다. 함수 본문에는 안정적인 바깥 스코프의 바인딩만 전달합니다. 매개변수,
지역 선언, 재대입, 삭제, 충돌 가능성이 있는 조건부 쓰기는 객체 소유 관계를 무효화합니다. 따라서 관계없는
`@cache.get(...)`을 메서드 이름만 보고 FastAPI 라우트로 분류하지 않습니다.

## 같은 파일의 라우터 prefix와 등록

같은 스코프에서 순서대로 선언한 지원 패턴에 대해 `APIRouter(prefix=...)`와
`include_router(..., prefix=...)`의 리터럴 값을 합성합니다.

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
users = APIRouter(prefix="/users")


@users.get("/me")
def current_user():
    pass


app.include_router(users, prefix="/api")
app.include_router(router=users, prefix="/internal")
```

이 코드는 `/api/users/me`와 `/internal/users/me`를 보고하며, 둘 다 원래 `current_user` 정의를 가리킵니다.
등록 전 경로인 `/users/me`를 중복 출력하지 않습니다. 반복 등록은 결과 경로가 같아도 각각 유지합니다.
자식의 라우트 선언과 포함 관계가 부모의 등록보다 앞에 있다면 같은 파일의 중첩 라우터 포함도 지원합니다.

prefix는 슬래시를 정규화하지 않고 그대로 이어 붙입니다. prefix 생략은 빈 문자열을 뜻합니다. 비어 있지
않은 prefix는 `/`로 시작하고 `/`로 끝나지 않아야 합니다. 문자열 리터럴만 해석하며, 동적인 값, 잘못된
prefix, `**kwargs` 전개를 추측하지 않습니다. `FastAPI(prefix=...)`를 APIRouter의 prefix로 취급하지 않습니다.

어디에도 포함되지 않은 독립 라우터는 생성자의 prefix를 포함한 상태로 소스 목록에 남습니다. 식별된 라우터가
포함 구문에서 참조되면 원래 선언 경로의 출력은 억제됩니다. 다른 등록을 해석할 수 없더라도 해석 가능한
등록은 유지합니다. 해석 불가능한 등록만 있는 라우터에 대해서는 경로를 추측하지 않습니다. 이 결과는 소스의
근거이며 배포 여부나 실제 접근 가능성을 보장하지 않습니다.

포함 구문보다 앞서 선언된 라우트와 중첩 포함 관계만 합성합니다. 이후 추가된 라우트는 해당 등록에 반영하지
않습니다. 이는 보수적으로 정한 지원 범위이며 모든 FastAPI 버전의 런타임 동작을 재현하는 것은 아닙니다.
포함 이후의 임의 변경과 스코프 사이의 합성은 지원을 미룹니다. 함수 내부 선언은 격리해서 분석하며, 함수를
분석한다고 해서 바깥 라우터에 그 함수의 부수 효과를 적용하지 않습니다.

프레임워크 사용 예시는 [FastAPI의 라우터 구성 가이드](https://fastapi.tiangolo.com/tutorial/bigger-applications/)를
참고하세요.

## 저장소 내부 import

저장소 스캔은 선택한 소스 트리와 일반적인 `src/` 디렉터리에서 모듈 색인을 만듭니다. 색인에 포함된 Python
파일만 참여합니다. Python 인터프리터의 import 기능, 설치된 패키지, `sys.path`, 네트워크를 이용하지 않으며
심볼릭 링크 파일과 디렉터리는 제외합니다.
일반 스캔은 `.git`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.venv`, `__pycache__`, `dist`,
`node_modules`, `venv`를 제외합니다. 다른 소스가 import한다고 해서 이 파일들이 후보에 추가되지 않습니다.
색인에 포함된 소스 트리로 구성되는 namespace package도 지원하므로 모든 디렉터리에 `__init__.py`가 있어야
하는 것은 아닙니다.

예를 들어 `app/routers/users.py`의 라우터를:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users")


@router.get("/me")
def current_user():
    pass
```

`app/main.py`에서 등록할 수 있습니다.

```python
from fastapi import FastAPI
from .routers.users import router as users_router

app = FastAPI()
app.include_router(users_router, prefix="/api")
```

결과는 `/api/users/me`이며, 파일과 줄 번호는 `app/routers/users.py`의 `current_user`를 가리킵니다.
라우터 파일도 함께 스캔했다는 이유로 원래 경로인 `/users/me`를 다시 출력하지 않습니다.

모듈 최상위의 정적인 절대 import와 패키지 상대 import를 지원합니다. 라우터를 직접 가져오는 import,
import 별칭, `from app.routers import users` 이후의 `users.router` 같은 모듈 참조, `__init__.py`를 거치는
import 기반 재노출이 포함됩니다. 중첩 등록과 반복 등록은 모듈 캐시에서 같은 라우터 객체를 공유합니다.
별도의 등록은 결과에서도 별도로 유지됩니다.

`import app.routers.users`처럼 명시적으로 점으로 연결된 모듈을 import했다면
`app.routers.users.router`로 참조할 수 있습니다. 패키지 초기화 파일은 `from . import users`로 자식 모듈을
재노출하거나 `from .users import router`로 라우터를 직접 재노출할 수 있습니다. `app`만 import했다고 모든
하위 모듈이 속성으로 존재한다고 가정하지 않습니다. 자식 모듈을 명시적으로 import하거나 정적으로 재노출해야
합니다. 패키지에서 `users`에 알 수 없는 값을 명시적으로 대입했다면 `from app import users`가 같은 위치의
`users.py` 모듈을 뜻한다고 추측하지 않습니다.

소스 파일과 완료된 모듈 분석은 한 번의 스캔 안에서 캐시됩니다. 다음 스캔은 새로 소스를 읽으며, 결과 순서는
파일 생성 순서에 의존하지 않습니다. 루트와 `src/`가 같은 모듈 이름에 서로 다른 후보를 제공하거나 파일과
같은 이름의 패키지가 충돌하면 import를 해석하지 않습니다. 순환 import에 속한 모듈은 일부만 초기화된
라우터 바인딩을 외부에 노출하지 않습니다.

없는 모듈, 충돌하는 모듈 이름, 순환 import, 와일드카드 import, 동적 import를 추측해서 해석하지 않습니다.
`fastapi`라는 로컬 모듈을 설치된 FastAPI 프레임워크로 간주하지 않습니다. import를 통해 색인에 없는 파일로
스캔 범위를 넓히지 않습니다. 지원하지 않는 import가 있으면 독립 선언이 소스 목록에 남을 수 있지만,
애플리케이션 등록이나 보안 판정을 뜻하지는 않습니다.

현재 파일 간 합성은 모듈 최상위에서 완료된 선언을 연결합니다. import한 라우터에 데코레이터를 추가하거나,
import한 객체를 변경 가능한 부모 라우터로 사용하거나, 나중에 실행될 함수 본문 안의 라우터 import를
연결하는 것은 지원 범위 밖입니다. 기존 함수 내부 분석은 격리된 상태로 유지됩니다. 독립적인 `parse_file`
진입점은 계속 단일 파일만 분석합니다.

지원 문법은 [Python의 import 형태](https://docs.python.org/3.12/reference/import.html#package-relative-imports)를
따르지만 AuthZest가 모든 런타임 import 동작을 재현하는 것은 아닙니다.

## 추후 지원할 패턴과 결과 해석

- 런타임 import hook, 외부 패키지 해석, 와일드카드 import, 모호하거나 순환하는 모듈.
- 스코프 사이의 라우터 합성과 포함 이후의 추가·변경.
- 다른 변수로 대입한 인스턴스·생성자 별칭, 팩토리 호출 결과 추론, 하위 클래스, 속성이나 컨테이너에 저장한
  객체.
- 클래스 본문, 조건문, 반복문, `try`, `with` 내부의 라우트. 이러한 블록이 관련 이름에 값을 쓰면 기존
  바인딩은 무효화될 수 있습니다.
- `global` 또는 `nonlocal`을 사용하는 함수 본문, 라우트 선언의 대입 표현식, 임의 함수 호출이나 reflection을
  통한 런타임 변경.
- 키워드로만 전달한 `path=`, 계산된 경로, `api_route`, `add_api_route`, WebSocket 선언.
- 의존성 수집, 인증·인가 판정, 보안 문제 발견 결과.

지원하지 않거나 해석되지 않는 선언은 라우트 목록에서 빠집니다. 보호됨, 보호되지 않음, 취약함으로 분류하지
않습니다. 보고서 스키마는 바뀌지 않았으며, 아직 미해석 선언 목록을 별도로 제공하지 않습니다. 따라서 결과가
비어 있다고 endpoint가 없거나 접근통제가 안전하다고 해석하면 안 됩니다. 문법 오류가 있거나 읽을 수 없는
소스는 계속 `parse_errors`에 나타납니다.

회귀 테스트는 [`test_parser.py`](../../tests/test_parser.py),
[`test_router_prefixes.py`](../../tests/test_router_prefixes.py),
[`test_cross_file_routes.py`](../../tests/test_cross_file_routes.py)에 있습니다. CLI, API, 저장소 runner
fixture도 공통 보고서 계약을 검증합니다. 이 소스 문법 범위를 넘는 FastAPI 버전 호환성은 주장하지 않습니다.
릴리스 절차는 [AuthZest 릴리스 관리](RELEASING.ko.md)를 참고하세요.
