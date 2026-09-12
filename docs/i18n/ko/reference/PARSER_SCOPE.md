# FastAPI 라우트 탐색

[문서](../INDEX.md) · [English](../../../reference/PARSER_SCOPE.md) · 한국어

이 문서는 [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2)에 도입하고
공개된 [v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3), 패키지
`0.1.0a3`에도 변경 없이 유지한 파서 범위를 설명합니다. FastAPI 객체 식별, prefix 합성, 저장소 내부 import,
버전이 있는 등록 근거와 직접·상속 의존성 선언은 해당 실행 파일에 포함되며
[alpha.2 변경 이력](../CHANGELOG.md#010-alpha2---2026-09-10)에 기록되어 있습니다. alpha.1 스캐폴딩에는 없습니다.
[릴리스 기록](../releases/RELEASING.md)에 정확한 커밋과 검증 범위를 남겼습니다.
이후 `main` 변경은 버전 문자열로 추정하지 말고 해당 태그와 비교하세요.

AuthZest는 Python 표준 라이브러리의 AST 파서로 Python 소스를 분석합니다. 분석 대상 애플리케이션을
import하거나 객체를 생성하거나 코드를 실행하지 않습니다. 지원 문법은 Python 3.12에서 테스트합니다.
단일 파일과 저장소 분석 모두 소스를 바이트로 읽어 Python이 UTF-8, UTF-8 byte order mark(BOM),
`# coding: latin-1` 같은 PEP 263 소스 인코딩 선언을 해석하도록 합니다. 잘못된 바이트열, 알 수 없는
인코딩, BOM과 인코딩 선언의 충돌은 파싱 오류로 보고합니다. 저장소 스캔은 나머지 읽을 수 있는
유효한 소스 파일의 분석을 계속합니다.

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
일반 스캔은 선택한 루트 내부에서 `.git`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.venv`,
`__pycache__`, `dist`, `node_modules`, `venv`라는 이름의 하위 디렉터리에 속한 소스 파일을 제외합니다.
명시적으로 선택한 스캔 루트와 그 상위 디렉터리는 이 이름 목록으로 제외하지 않습니다. 따라서 루트 이름이
`dist`이거나 `dist`라는 상위 디렉터리 아래에 프로젝트가 있어도 대상 소스를 분석합니다. 해당 루트 안에
있는 별도의 하위 `dist` 디렉터리는 계속 제외합니다. 다른 소스가 import한다고 해서 제외된 파일이 후보에
추가되지는 않습니다. 색인에 포함된 소스 트리로 구성되는 namespace package도 지원하므로 모든
디렉터리에 `__init__.py`가 있어야 하는 것은 아닙니다.

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

## 라우트 직접 의존성 선언

지원하는 route의 매개변수 기본값, 인라인 `Annotated` 메타데이터와 route decorator의 리터럴
`dependencies` 목록에서 직접 `Depends`·`Security` 호출을 기록합니다. 인증·인가 분류가 아니라
선언 사실입니다. 예를 들면 다음과 같습니다.

```python
from typing import Annotated
from fastapi import Depends, FastAPI, Security

app = FastAPI()


@app.get("/items", dependencies=[Depends(trace_request)])
def items(
    page: Annotated[dict, Depends(pagination)],
    context=Security(example_context, scopes=["items:read"]),
):
    pass
```

이 코드는 선언 구문만 보여주며 대상 이름은 여기 정의하지 않았고 파서도 callable을 조회하거나
실행하지 않습니다. 런타임에 없는 단순/점 연결 이름도 구문상 `reference`일 수 있습니다.
일반 DI는 보안 관련 이름과 같은 방식으로 기록합니다. `Security`, scope 문자열이나
`get_current_user`라는 함수명이 접근통제 증거는 아닙니다.
직접 관리하는 [의존성 예제](../guides/EXAMPLES.md)에는 일반 샘플 함수와 예상 출력이 있습니다.

지원하는 factory import는 `from fastapi import Depends as D, Security as S`, `import fastapi`,
`import fastapi as fa`입니다. 인라인 `Annotated`는 `typing`과 `typing_extensions`의 직접 import 및
모듈 별칭으로 인식합니다. 바인딩 변경과 이름 가림을 반영하며 사용자 객체가 `Depends`라는 이름을
가졌다는 이유로 인식하지 않습니다. 저장소 분석은 로컬 framework/typing 모듈 이름 가림과 지원하는
import 재수출도 반영합니다. 대상 callable의 import 해석은 이 기능의 범위가 아닙니다.

Python 3.12 함수 type parameter는 해당 함수의 annotation과 본문에서 같은 이름을 가리지만 매개변수
기본값이나 decorator에서는 가리지 않습니다. 소스 분석에서 이 맥락들의 바인딩을 구분하며 type parameter나
annotation을 런타임 평가하지 않습니다.

매개변수 근거는 위치 전용·일반·키워드 전용 기본값과 인라인 매개변수 annotation의 직접 인식한
메타데이터를 다룹니다. `Annotated`의 첫 type 인자가 아닌 그 뒤의 메타데이터만 의존성 위치입니다.
한 매개변수의 직접 의존성 선언이 여러 개면 런타임 우선순위를 추측하지 않고 미해석으로 보존합니다.
확인한 의존성 포함 type alias와 중첩 annotation은 진단하지만 펼치지 않으며 문자열 annotation은 평가하지 않습니다.
alias 진단은 단순/annotation 대입이나 Python 3.12 type alias의 인식한 `Annotated` 값과 이미 알려진
alias의 단순 재대입으로 제한됩니다. 모든 alias나 재귀 타입 표현식을 찾지 않습니다. 첫 type 인자의
일반 의존성 호출은 메타데이터가 아니며, 그 위치의 확인한 중첩 의존성 포함 `Annotated`는 펼치지 않고 진단합니다.

decorator의 `dependencies`는 리터럴 목록, 빈 목록이나 `None`을 지원합니다. 인식한 직접 항목은
수집하고 동적 목록·확장/미확인 항목·반복 인자는 진단합니다. 겹친 decorator마다 공통 매개변수 근거와
해당 decorator 자신의 의존성만 기록합니다. 원본 소스 줄과 UTF-8 바이트 열 순서로 정렬합니다.
같은 파일과 파일 간 mount는 원본 라우트 직접 근거를 유지합니다. 적용 목록은 아래의 지원 상속 맥락을 더합니다.

대상은 위치 인자 하나 또는 `dependency=...`로 지정할 수 있습니다. 단순/점 연결 이름은 구문상 지원하며
생략·`None` 대상, factory 호출, lambda와 기타 동적 대상은 미해석입니다. 표현식은 AST로 정규화하고
실행하지 않습니다. 확장·중복·미확인 인자와 추가 위치 인자는 미해석입니다. `use_cache`와 `Depends`의
`scope` 키워드는 허용하지만 런타임 동작을 해석하지 않습니다. `Security` scopes는 리터럴 문자열 목록,
생략이나 명시적인 `None`만 확인하며 생략/`None`은 빈 목록입니다. 동적/잘못된 scopes는 사유와 null을
유지합니다. 의존성 근거만 partial이면 route 자체는 보존합니다.

이 제한된 구문은 FastAPI의 [의존성 참조](https://fastapi.tiangolo.com/reference/dependencies/),
[의존성 안내](https://fastapi.tiangolo.com/tutorial/dependencies/)와
[decorator 의존성 안내](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/)를
참고합니다. AuthZest는 모든 framework·Python 런타임 동작을 재현하지 않습니다.

## 상속 등록 맥락

식별한 `FastAPI(...)`·`APIRouter(...)` 생성자와 지원하는 `include_router(...)` 호출의 리터럴
`dependencies` 목록도 수집합니다. 같은 직접 호출/import와 대상/scopes 규칙을 적용합니다.
선언 위치 종류는 `application`, `router`, `include`이며 받는 handler가 아니라 원본 의존성 호출의
위치를 유지합니다. 생략·`None`·빈 리터럴 목록은 그 위치에서 선언이 없다는 뜻입니다. 동적 목록과
미지원 항목은 의존성을 추측하지 않고 기존 의존성 진단을 사용하며 확인한 route는 partial 분석으로 유지합니다.

`effective_dependencies`에는 바깥 owner 선언, 해당 include 위치 선언, 차례로 안쪽 owner/include
맥락과 마지막 원본 라우트 직접 `dependencies`가 들어갑니다. 맥락별 소스 순서를 유지하며 중복을
제거하거나 전체를 재정렬하지 않습니다. 독립 router도 자체 생성자 근거를 유지합니다. 지원하는 저장소
내부 파일 간 import를 포함한 중첩·반복 mount는 원본 항목과 각 등록의 별도 app/include 근거를 유지합니다.
기존 `dependencies` 목록을 상속 목록으로 바꾸지 않습니다.

기존 제한된 합성 규칙을 그대로 따릅니다. 이미 선언한 지원 route/include chain만 합성하고 미지원·순환·
교차 scope include 시도는 미해석으로 남습니다. 이런 미합성 include 시도의 의존성 진단은 완전하지 않으며
기존 include 진단이 지원하는 근거입니다. 런타임 override, 임의 owner 변경, factory 결과와 callable
하위 의존성 그래프는 여전히 범위 밖입니다. 적용 순서는 소스 맥락이며 FastAPI 실행 순서, cache 재사용이나
인증·인가 증명이 아닙니다. [상속 예제](../guides/EXAMPLES.md)를 참고하세요.

## 등록 근거와 진단

공통 리포트는 `schema_version: "1.2"`를 사용합니다. 이 리포트 스키마 버전은 Python 패키지 및
릴리스 버전과 별개입니다. 기존 라우트 필드와 `parse_errors`를 유지하며, `analysis_status`,
`diagnostics`, 각 라우트의 `registration_id`와 `registration`은 1.0에 추가했습니다.
1.1에는 각 라우트의 `dependencies`를, 1.2에는 `effective_dependencies`를 추가했습니다.
두 의존성 목록 모두 등록 ID 해시를 바꾸지 않습니다.
각 필드의 표현과 호환성 규칙은 [리포트 계약](REPORT_CONTRACT.md)에 정의되어 있습니다.

파서가 생성하는 모든 라우트에는 원본 데코레이터와 객체 생성자의 위치가 기록됩니다. 해석된 등록에는
알려진 경우 애플리케이션 객체와 각 `include_router` 구문의 위치, 부모 객체, 자식 라우터, 리터럴
include prefix도 기록합니다. include chain은 가장 바깥 등록(애플리케이션 또는 라우터)부터 가장 안쪽
라우터 순서입니다. 독립 라우터에는 애플리케이션 객체 없이 비어 있지 않은 chain이 있을 수 있습니다.
기존 라우트의 `file`과 `line`은 계속 등록 구문이 아닌 원래 handler 정의를 가리킵니다. 리포트 JSON의 새
위치 필드는 저장소 상대 POSIX 경로, 1부터 시작하는 줄 번호, 1부터 시작하는 UTF-8 바이트 열 번호를
사용합니다. 알 수 없는 위치 값은 `null`입니다.

등록 ID는 같은 상대 디렉터리 구조에서 소스 근거가 바뀌지 않으면 일정하게 유지됩니다. 별도의
애플리케이션, 여러 데코레이터, 반복 등록은 경로와 HTTP 메서드가 같아도 구별되며, 같은 줄의 여러
등록 호출도 각각 구별합니다. ID는 소스 등록을 식별할 뿐 런타임 객체, 전체 소스 내용의 해시나 승인
토큰이 아닙니다. 선언을 옮기거나 기록되는 등록 근거를 바꾸면 ID도 바뀔 수 있습니다.

함수 본문의 목록은 `execution_scope: "deferred"`, 모듈 최상위 목록은 `"module"`로 표시합니다.
상속해서 참조한 객체도 원래 생성자 위치를 유지합니다. 어느 표시도 실제 실행이 해당 선언에
도달하거나 결과 라우트가 배포되었다는 증거는 아닙니다.

진단에는 사유 `code`, 설명 `message`, 원본 `location`, `severity`가 포함됩니다. 제한된 파서는
지원하는 탐색 문법을 확장하지 않고 다음과 같이 확인된 사례를 보고합니다.

- `source-read-error`, `source-parse-error`, `source-decode-error`는 소스를 읽고 파싱하는 과정의
  실패를 나타냅니다. 기존 `parse_errors` 텍스트도 이 오류 진단과 함께 유지합니다.
- `unsupported-owner-construction`은 식별된 생성자의 인자나 prefix를 해석할 수 없음을 나타냅니다.
- `dynamic-route-path`, `unsupported-route-arguments`, `unsupported-route-expression`,
  `unsupported-route-owner`는 식별된 라우트 객체에서 해석되지 않은 선언을 설명합니다.
- `dynamic-include-prefix`, `unsupported-include-arguments`, `unsupported-include-context`,
  `unresolved-include-owner`, `include-cycle`은 확인된 미지원 포함 시도를 설명합니다.
- `conditional-registration`은 지원하지 않는 제어 흐름 안의 식별된 객체에 대한 라우트 선언을 표시합니다.
- `unsupported-dependency-list`는 지원 decorator·생성자·include 호출의 리터럴이 아니거나 반복한 의존성 목록,
  `unsupported-dependency-entry`는 인식한 직접 의존성 호출이 아닌 항목입니다.
- `unsupported-dependency-expression`, `unsupported-dependency-annotation`,
  `unsupported-dependency-metadata`는 지원하지 않는 기본값/annotation 형태의 알려진 의존성 호출이나
  펼치지 않는 의존성 포함 alias를 나타냅니다.
- `unsupported-dependency-arguments`는 확장·중복·추가 위치·미확인 호출 인자입니다.
  `unresolved-dependency-target`은 생략 또는 이름이 아닌 대상, `dynamic-security-scopes`는 확인한
  문자열 목록으로 표현할 수 없는 scopes입니다. `ambiguous-dependency-declaration`은 한 매개변수에
  직접 선언이 여러 개 있음을 나타내며 framework가 무엇을 선택할지 추측하지 않습니다.

예를 들어 순환 import 때문에 식별된 app의 `include_router`에서 자식 라우터를 해석하지 못할 수
있습니다. 이때 진단은 import가 성공했다고 주장하지 않고 해당 include 호출을 가리킵니다. 알 수 없는
임의의 `.get(...)` 객체나 무관한 import는 이름만을 이유로 프레임워크 진단을 만들지 않습니다.
진단은 지원하지 않는 모든 Python 패턴의 완전한 목록이 아닙니다.
의존성 진단은 warning이며 route 경로가 확인돼도 리포트를 partial로 만듭니다. 근거 항목을 만드는
호출은 `unresolved_reasons`에도 사유 코드를 보존합니다. 동적 목록이나 미지원 중첩 annotation은 의존성
항목 없이 진단만 만들 수 있습니다. scopes 진단은 OAuth 실패 판정이 아니며 빈 의존성 목록은 공개 route label이 아닙니다.

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
- 중첩 callable 의존성 그래프, 대상 callable 해석, 런타임 override, 인증·인가 판정과 보안 문제 발견 결과.

지원하지 않거나 해석되지 않는 route 선언은 목록에서 빠집니다. 지원 route의 의존성 근거가 미해석이면
진단과 함께 route를 유지합니다. 보호됨, 보호되지 않음, 취약함으로
분류하지 않습니다. 진단이나 파싱 오류가 있으면 `analysis_status: "partial"`, 없으면 `"bounded"`이며,
어느 경우도 분석이 완전하다고 주장하지 않습니다. 빈 결과, 빈 진단 목록, 성공 종료는 endpoint가
없거나 접근통제가 안전하다는 증거가 아닙니다.

텍스트 CLI는 진단 상세를 stderr로 출력하고 부분 목록임을 표시하며, JSON은 기존 `parse_errors`
배열과 구조화된 진단을 함께 제공합니다. 기본 스캔은 부분 리포트를 포함해 리포트를 생성했으면 계속
종료 코드 0을 반환합니다. `--strict`를 사용하면 부분 리포트를 출력한 뒤 종료 코드 1을 반환합니다.
잘못된 저장소 입력은 종료 코드 2를 반환합니다. 로컬 scan API는 생성된 부분 리포트에 HTTP 200을
반환하므로 호출자는 `analysis_status`와 `diagnostics`를 확인해야 합니다. 전체 출력 및 종료 코드
정책은 [리포트 계약](REPORT_CONTRACT.md)을 참고하세요.

회귀 테스트는 [`test_parser.py`](../../../../tests/test_parser.py),
[`test_router_prefixes.py`](../../../../tests/test_router_prefixes.py),
[`test_cross_file_routes.py`](../../../../tests/test_cross_file_routes.py),
[`test_source_encodings.py`](../../../../tests/test_source_encodings.py),
[`test_report_parser.py`](../../../../tests/test_report_parser.py)에 있습니다. CLI, API, 저장소 runner
fixture도 공통 보고서 계약을 검증합니다. 라우트 직접 의존성 전달 계층 사례는
[`test_dependency_transports.py`](../../../../tests/test_dependency_transports.py)에 있습니다.
이 소스 문법 범위를 넘는 FastAPI 버전 호환성은 주장하지 않습니다.
릴리스 절차는 [AuthZest 릴리스 관리](../releases/RELEASING.md)를 참고하세요.
