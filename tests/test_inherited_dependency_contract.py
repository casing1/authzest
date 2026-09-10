import json
from dataclasses import replace
from pathlib import Path

import pytest

from authzest.models import (
    DependencyEvidence,
    DependencyLevel,
    OwnerEvidence,
    RegistrationEvidence,
    Route,
    ScanReport,
    SourceLocation,
)


def evidence(root: Path, target: str, level: DependencyLevel, line: int) -> DependencyEvidence:
    return DependencyEvidence(
        kind="Depends",
        target=target,
        location=SourceLocation(root / "api" / "main.py", line, 28),
        declaration_level=level,
    )


def route_with_evidence(root: Path) -> Route:
    path = root / "api" / "main.py"
    owner = OwnerEvidence("FastAPI", SourceLocation(path, 2, 7))
    return Route(
        path="/users",
        methods=("GET",),
        function="users",
        file=path,
        line=8,
        registration=RegistrationEvidence(SourceLocation(path, 7, 2), owner, owner),
        dependencies=(evidence(root, "local_provider", "decorator", 7),),
        inherited_dependencies=(evidence(root, "application_provider", "application", 2),),
    )


@pytest.mark.parametrize("level", ["application", "router", "include"])
def test_inherited_declaration_levels_preserve_the_existing_evidence_shape(
    tmp_path: Path, level: DependencyLevel
) -> None:
    item = evidence(tmp_path, "policy.context", level, 4)

    assert item.to_dict(tmp_path) == {
        "kind": "Depends",
        "target": "policy.context",
        "location": {"file": "api/main.py", "line": 4, "column": 28},
        "declaration_level": level,
        "parameter": None,
        "resolution": "reference",
        "scopes": None,
        "unresolved_reasons": [],
    }


def test_legacy_route_defaults_keep_local_and_effective_evidence_empty(tmp_path: Path) -> None:
    route = Route("/health", ("GET",), "health", tmp_path / "main.py", 4)
    payload = route.to_dict(tmp_path)

    assert route.dependencies == route.inherited_dependencies == route.effective_dependencies == ()
    assert payload["dependencies"] == payload["effective_dependencies"] == []
    assert "inherited_dependencies" not in payload
    assert payload["registration_id"] is None


def test_effective_view_is_inherited_then_local_without_serializing_internal_storage(
    tmp_path: Path,
) -> None:
    route = route_with_evidence(tmp_path)
    payload = route.to_dict(tmp_path)

    assert route.effective_dependencies == (*route.inherited_dependencies, *route.dependencies)
    assert payload["dependencies"] == [route.dependencies[0].to_dict(tmp_path)]
    assert payload["effective_dependencies"] == [
        item.to_dict(tmp_path) for item in route.effective_dependencies
    ]
    assert "inherited_dependencies" not in payload
    assert json.loads(json.dumps(payload)) == payload


def test_effective_evidence_preserves_duplicates_and_context_order(tmp_path: Path) -> None:
    application = evidence(tmp_path, "shared_provider", "application", 20)
    include = evidence(tmp_path, "shared_provider", "include", 40)
    router = evidence(tmp_path, "shared_provider", "router", 2)
    local = evidence(tmp_path, "shared_provider", "decorator", 8)
    route = replace(
        route_with_evidence(tmp_path),
        inherited_dependencies=(application, include, router, router),
        dependencies=(local, local),
    )

    assert route.effective_dependencies == (application, include, router, router, local, local)
    assert len(route.to_dict(tmp_path)["effective_dependencies"]) == 6


def test_inherited_evidence_does_not_change_the_registration_identity(tmp_path: Path) -> None:
    route = route_with_evidence(tmp_path)
    original = route.to_dict(tmp_path)
    variants = [
        replace(route, inherited_dependencies=()),
        replace(
            route,
            inherited_dependencies=(evidence(tmp_path, "new_provider", "application", 25),),
        ),
        replace(route, inherited_dependencies=tuple(reversed(route.effective_dependencies))),
    ]

    for variant in variants:
        payload = variant.to_dict(tmp_path)
        assert payload["registration_id"] == original["registration_id"]
        assert payload["dependencies"] == original["dependencies"]
        assert payload["effective_dependencies"] != original["effective_dependencies"]


def test_inherited_source_locations_and_reports_survive_root_relocation(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "different" / "second"
    first = route_with_evidence(first_root)
    second = route_with_evidence(second_root)

    assert first.to_dict(first_root) == second.to_dict(second_root)
    assert not first_root.exists()
    assert not second_root.exists()


def test_report_schema_adds_the_effective_view_without_changing_local_meaning(
    tmp_path: Path,
) -> None:
    route = route_with_evidence(tmp_path)
    payload = ScanReport(tmp_path, python_files=1, routes=(route,)).to_dict()

    assert payload["schema_version"] == "1.2"
    assert payload["analysis_status"] == "bounded"
    assert payload["diagnostics"] == []
    assert len(payload["routes"][0]["dependencies"]) == 1
    assert len(payload["routes"][0]["effective_dependencies"]) == 2
