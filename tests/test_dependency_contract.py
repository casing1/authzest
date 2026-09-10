import json
from dataclasses import replace
from pathlib import Path

import pytest

from authzest.models import (
    DependencyEvidence,
    OwnerEvidence,
    RegistrationEvidence,
    Route,
    ScanReport,
    SourceLocation,
)


def dependency(root: Path) -> DependencyEvidence:
    return DependencyEvidence(
        kind="Depends",
        target="policies.current_user",
        location=SourceLocation(root / "api" / "users.py", 8, 24),
        declaration_level="parameter-default",
        parameter="user",
    )


def registered_route(root: Path) -> Route:
    location = SourceLocation(root / "api" / "users.py", 3, 7)
    owner = OwnerEvidence("FastAPI", location)
    return Route(
        "/users",
        ("GET",),
        "users",
        location.file,
        8,
        registration=RegistrationEvidence(
            SourceLocation(location.file, 7, 2), owner, application=owner
        ),
    )


def test_dependency_evidence_serializes_all_fields_without_runtime_claims(tmp_path: Path) -> None:
    evidence = dependency(tmp_path)

    assert evidence.to_dict(tmp_path) == {
        "kind": "Depends",
        "target": "policies.current_user",
        "location": {"file": "api/users.py", "line": 8, "column": 24},
        "declaration_level": "parameter-default",
        "parameter": "user",
        "resolution": "reference",
        "scopes": None,
        "unresolved_reasons": [],
    }
    assert evidence.to_dict()["location"]["file"] == (tmp_path / "api" / "users.py").as_posix()
    assert json.loads(json.dumps(evidence.to_dict(tmp_path))) == evidence.to_dict(tmp_path)


@pytest.mark.parametrize("scopes", [(), ("read:users",), ("사용자:읽기", "read:users")])
def test_security_scope_lists_preserve_empty_unicode_and_declared_order(
    tmp_path: Path, scopes: tuple[str, ...]
) -> None:
    evidence = replace(
        dependency(tmp_path),
        kind="Security",
        declaration_level="parameter-annotation",
        scopes=scopes,
    )

    assert evidence.to_dict(tmp_path)["scopes"] == list(scopes)


def test_unresolved_target_and_scopes_are_not_serialized_as_empty_success(tmp_path: Path) -> None:
    evidence = DependencyEvidence(
        kind="Security",
        target=None,
        location=SourceLocation(tmp_path / "main.py", 4, 30),
        declaration_level="decorator",
        resolution="unresolved",
        scopes=None,
        unresolved_reasons=("unresolved-dependency-target", "dynamic-security-scopes"),
    )
    payload = evidence.to_dict(tmp_path)

    assert payload["target"] is None
    assert payload["parameter"] is None
    assert payload["scopes"] is None
    assert payload["resolution"] == "unresolved"
    assert payload["unresolved_reasons"] == [
        "unresolved-dependency-target",
        "dynamic-security-scopes",
    ]


def test_old_route_constructors_default_to_an_empty_dependency_list(tmp_path: Path) -> None:
    route = Route("/health", ("GET",), "health", tmp_path / "main.py", 4)

    assert route.dependencies == ()
    assert route.to_dict(tmp_path)["dependencies"] == []
    assert route.to_dict(tmp_path)["registration"] is None
    assert route.to_dict(tmp_path)["registration_id"] is None


def test_dependency_changes_do_not_change_a_registration_identity(tmp_path: Path) -> None:
    route = registered_route(tmp_path)
    evidence = dependency(tmp_path)
    variants = [
        route,
        replace(route, dependencies=(evidence,)),
        replace(route, dependencies=(replace(evidence, target="policies.admin"),)),
        replace(route, dependencies=(evidence, evidence)),
        replace(
            route,
            dependencies=(
                replace(evidence, resolution="unresolved", unresolved_reasons=("unsupported",)),
            ),
        ),
    ]

    assert len({variant.to_dict(tmp_path)["registration_id"] for variant in variants}) == 1
    assert len({json.dumps(variant.to_dict(tmp_path)) for variant in variants}) == len(variants)


def test_dependency_reports_relocate_without_reading_source_files(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "nested" / "second"
    first = replace(registered_route(first_root), dependencies=(dependency(first_root),))
    second = replace(registered_route(second_root), dependencies=(dependency(second_root),))

    assert first.to_dict(first_root) == second.to_dict(second_root)
    assert not first_root.exists()
    assert not second_root.exists()


def test_additive_dependency_schema_does_not_conflate_references_with_diagnostics(
    tmp_path: Path,
) -> None:
    evidence = dependency(tmp_path)
    report = ScanReport(
        root=tmp_path,
        python_files=1,
        routes=(replace(registered_route(tmp_path), dependencies=(evidence,)),),
    )
    payload = report.to_dict()

    assert payload["schema_version"] == "1.2"
    assert payload["analysis_status"] == "bounded"
    assert payload["diagnostics"] == []
    assert payload["routes"][0]["dependencies"] == [evidence.to_dict(tmp_path)]
