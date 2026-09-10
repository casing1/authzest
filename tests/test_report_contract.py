import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from authzest.models import (
    Diagnostic,
    IncludeSite,
    OwnerEvidence,
    RegistrationEvidence,
    Route,
    ScanReport,
    SourceLocation,
)


def registered_route(root: Path) -> Route:
    application = OwnerEvidence(
        kind="FastAPI",
        location=SourceLocation(root / "main.py", line=4, column=6),
    )
    parent_router = OwnerEvidence(
        kind="APIRouter",
        location=SourceLocation(root / "api" / "router.py", line=3, column=9),
    )
    owner = OwnerEvidence(
        kind="APIRouter",
        location=SourceLocation(root / "api" / "users.py", line=3, column=9),
    )
    registration = RegistrationEvidence(
        declaration=SourceLocation(root / "api" / "users.py", line=10, column=1),
        owner=owner,
        application=application,
        include_chain=(
            IncludeSite(
                location=SourceLocation(root / "main.py", line=9, column=1),
                parent=application,
                router=parent_router,
                prefix="/v1",
            ),
            IncludeSite(
                location=SourceLocation(root / "api" / "router.py", line=7, column=1),
                parent=parent_router,
                router=owner,
                prefix="/admin",
            ),
        ),
    )
    return Route(
        path="/v1/admin/users",
        methods=("GET",),
        function="list_users",
        file=root / "api" / "users.py",
        line=11,
        registration=registration,
    )


def test_legacy_custom_routes_keep_fields_without_inventing_registration(tmp_path: Path) -> None:
    route = Route("/health", ("GET", "HEAD"), "health", tmp_path / "main.py", 8)

    assert route.to_dict(tmp_path) == {
        "path": "/health",
        "methods": ["GET", "HEAD"],
        "function": "health",
        "file": "main.py",
        "line": 8,
        "registration_id": None,
        "registration": None,
        "dependencies": [],
        "effective_dependencies": [],
    }


def test_evidence_serializes_source_coordinates_and_outer_to_inner_chain(tmp_path: Path) -> None:
    route = registered_route(tmp_path)
    payload = route.to_dict(tmp_path)

    assert payload["file"] == str(Path("api/users.py"))
    assert payload["registration"] == {
        "declaration": {"file": "api/users.py", "line": 10, "column": 1},
        "owner": {
            "kind": "APIRouter",
            "location": {"file": "api/users.py", "line": 3, "column": 9},
        },
        "application": {
            "kind": "FastAPI",
            "location": {"file": "main.py", "line": 4, "column": 6},
        },
        "include_chain": [
            {
                "location": {"file": "main.py", "line": 9, "column": 1},
                "parent": {
                    "kind": "FastAPI",
                    "location": {"file": "main.py", "line": 4, "column": 6},
                },
                "router": {
                    "kind": "APIRouter",
                    "location": {"file": "api/router.py", "line": 3, "column": 9},
                },
                "prefix": "/v1",
            },
            {
                "location": {"file": "api/router.py", "line": 7, "column": 1},
                "parent": {
                    "kind": "APIRouter",
                    "location": {"file": "api/router.py", "line": 3, "column": 9},
                },
                "router": {
                    "kind": "APIRouter",
                    "location": {"file": "api/users.py", "line": 3, "column": 9},
                },
                "prefix": "/admin",
            },
        ],
        "execution_scope": "module",
    }
    assert json.loads(json.dumps(payload)) == payload


def test_source_location_preserves_unknown_coordinates(tmp_path: Path) -> None:
    location = SourceLocation(tmp_path / "api" / "unreadable.py", line=None)

    assert location.to_dict(tmp_path) == {
        "file": "api/unreadable.py",
        "line": None,
        "column": None,
    }
    assert location.to_dict() == {
        "file": (tmp_path / "api" / "unreadable.py").as_posix(),
        "line": None,
        "column": None,
    }


def test_unmounted_registration_does_not_invent_an_application(tmp_path: Path) -> None:
    owner = OwnerEvidence("APIRouter", SourceLocation(tmp_path / "router.py", 2))
    evidence = RegistrationEvidence(SourceLocation(tmp_path / "router.py", 5), owner)

    assert evidence.to_dict(tmp_path) == {
        "declaration": {"file": "router.py", "line": 5, "column": None},
        "owner": {
            "kind": "APIRouter",
            "location": {"file": "router.py", "line": 2, "column": None},
        },
        "application": None,
        "include_chain": [],
        "execution_scope": "module",
    }


def test_registration_id_is_the_documented_canonical_sha256(tmp_path: Path) -> None:
    route = replace(registered_route(tmp_path), path="/v1/admin/사용자")
    payload = route.to_dict(tmp_path)
    canonical = {
        "path": route.path,
        "methods": list(route.methods),
        "function": route.function,
        "file": "api/users.py",
        "line": route.line,
        "registration": payload["registration"],
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()

    assert payload["registration_id"] == f"route-{digest}"


def test_registered_route_ids_and_evidence_are_stable_across_root_relocation(
    tmp_path: Path,
) -> None:
    original_root = tmp_path / "original"
    relocated_root = tmp_path / "different" / "location"
    original = registered_route(original_root)
    relocated = registered_route(relocated_root)

    assert original.to_dict(original_root) == relocated.to_dict(relocated_root)
    assert original.to_dict(original_root) == original.to_dict(original_root)
    assert not original_root.exists()
    assert not relocated_root.exists()


@pytest.mark.parametrize(
    "metadata",
    [
        {"path": "/v2/admin/users"},
        {"methods": ("POST",)},
        {"function": "other_handler"},
        {"line": 12},
    ],
    ids=["path", "method", "handler", "handler-line"],
)
def test_route_metadata_changes_the_registration_id(tmp_path: Path, metadata: dict) -> None:
    route = registered_route(tmp_path)

    assert (
        replace(route, **metadata).to_dict(tmp_path)["registration_id"]
        != route.to_dict(tmp_path)["registration_id"]
    )


def test_handler_source_file_changes_the_registration_id(tmp_path: Path) -> None:
    route = registered_route(tmp_path)
    changed = replace(route, file=tmp_path / "admin" / "users.py")

    assert (
        changed.to_dict(tmp_path)["registration_id"] != route.to_dict(tmp_path)["registration_id"]
    )


@pytest.mark.parametrize("coordinate", ["line", "column"])
def test_distinct_include_sites_have_distinct_ids_even_for_identical_routes(
    tmp_path: Path, coordinate: str
) -> None:
    route = registered_route(tmp_path)
    evidence = route.registration
    assert evidence is not None
    outer, inner = evidence.include_chain
    location = replace(outer.location, **{coordinate: 20})
    changed = replace(
        route,
        registration=replace(evidence, include_chain=(replace(outer, location=location), inner)),
    )

    before = route.to_dict(tmp_path)
    after = changed.to_dict(tmp_path)
    assert {key: before[key] for key in ("path", "methods", "function", "file", "line")} == {
        key: after[key] for key in ("path", "methods", "function", "file", "line")
    }
    assert before["registration_id"] != after["registration_id"]


@pytest.mark.parametrize(
    "component", ["declaration", "owner", "application", "include-parent", "include-order", "scope"]
)
def test_registration_context_changes_the_id(tmp_path: Path, component: str) -> None:
    route = registered_route(tmp_path)
    evidence = route.registration
    assert evidence is not None
    if component == "declaration":
        changed_evidence = replace(evidence, declaration=replace(evidence.declaration, column=2))
    elif component == "owner":
        changed_evidence = replace(
            evidence,
            owner=replace(evidence.owner, location=SourceLocation(tmp_path / "other.py", 3)),
        )
    elif component == "application":
        changed_evidence = replace(evidence, application=None)
    elif component == "include-parent":
        outer, inner = evidence.include_chain
        parent = replace(outer.parent, location=SourceLocation(tmp_path / "other.py", 4))
        changed_evidence = replace(evidence, include_chain=(replace(outer, parent=parent), inner))
    elif component == "include-order":
        changed_evidence = replace(evidence, include_chain=tuple(reversed(evidence.include_chain)))
    else:
        changed_evidence = replace(evidence, execution_scope="deferred")
    changed_route = replace(route, registration=changed_evidence)

    assert (
        changed_route.to_dict(tmp_path)["registration_id"]
        != route.to_dict(tmp_path)["registration_id"]
    )


@pytest.mark.parametrize("has_routes", [False, True])
def test_reports_without_known_diagnostics_are_bounded_not_security_passes(
    tmp_path: Path, has_routes: bool
) -> None:
    routes = (registered_route(tmp_path),) if has_routes else ()
    report = ScanReport(root=tmp_path, python_files=3, routes=routes)
    payload = report.to_dict()

    assert set(payload) == {
        "schema_version",
        "analysis_status",
        "root",
        "python_files",
        "route_count",
        "routes",
        "parse_errors",
        "codex_status",
        "diagnostics",
    }
    assert payload["schema_version"] == "1.2"
    assert payload["analysis_status"] == "bounded"
    assert payload["root"] == str(tmp_path)
    assert payload["python_files"] == 3
    assert payload["route_count"] == len(routes)
    assert payload["parse_errors"] == []
    assert payload["codex_status"] == "disabled"
    assert payload["diagnostics"] == []


@pytest.mark.parametrize("severity", ["warning", "error"])
def test_known_diagnostics_make_reports_partial_without_removing_routes(
    tmp_path: Path, severity: str
) -> None:
    diagnostic = Diagnostic(
        code="dynamic_prefix",
        message="A router prefix could not be resolved statically.",
        location=SourceLocation(tmp_path / "api" / "router.py", line=7, column=1),
        severity=severity,
    )
    route = registered_route(tmp_path)
    report = ScanReport(tmp_path, 3, routes=(route,), diagnostics=(diagnostic,))
    payload = report.to_dict()

    assert payload["analysis_status"] == "partial"
    assert payload["route_count"] == 1
    assert payload["routes"] == [route.to_dict(tmp_path)]
    assert payload["parse_errors"] == []
    assert payload["diagnostics"] == [
        {
            "code": "dynamic_prefix",
            "message": "A router prefix could not be resolved statically.",
            "location": {"file": "api/router.py", "line": 7, "column": 1},
            "severity": severity,
        }
    ]
    assert json.loads(json.dumps(payload)) == payload


def test_legacy_parse_errors_alone_still_make_the_report_partial(tmp_path: Path) -> None:
    error = "main.py: source could not be parsed"
    report = ScanReport(tmp_path, 1, parse_errors=(error,))

    payload = report.to_dict()

    assert payload["analysis_status"] == "partial"
    assert payload["parse_errors"] == [error]
    assert payload["diagnostics"] == []


def test_diagnostic_default_severity_and_missing_line_are_explicit(tmp_path: Path) -> None:
    diagnostic = Diagnostic(
        "source_read_error", "Source is unreadable.", SourceLocation(tmp_path / "main.py", None)
    )

    assert diagnostic.to_dict(tmp_path) == {
        "code": "source_read_error",
        "message": "Source is unreadable.",
        "location": {"file": "main.py", "line": None, "column": None},
        "severity": "warning",
    }
