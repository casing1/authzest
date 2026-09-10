from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

REPORT_SCHEMA_VERSION = "1.1"


def _source_path(path: Path, root: Path | None) -> Path:
    if root is not None:
        with suppress(ValueError):
            return path.relative_to(root)
    return path


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Original source position; columns are one-based UTF-8 byte offsets."""

    file: Path
    line: int | None
    column: int | None = None

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        return {
            "file": _source_path(self.file, root).as_posix(),
            "line": self.line,
            "column": self.column,
        }


@dataclass(frozen=True, slots=True)
class OwnerEvidence:
    kind: Literal["FastAPI", "APIRouter"]
    location: SourceLocation

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        return {"kind": self.kind, "location": self.location.to_dict(root)}


@dataclass(frozen=True, slots=True)
class IncludeSite:
    location: SourceLocation
    parent: OwnerEvidence
    router: OwnerEvidence
    prefix: str

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(root),
            "parent": self.parent.to_dict(root),
            "router": self.router.to_dict(root),
            "prefix": self.prefix,
        }


@dataclass(frozen=True, slots=True)
class RegistrationEvidence:
    declaration: SourceLocation
    owner: OwnerEvidence
    application: OwnerEvidence | None = None
    include_chain: tuple[IncludeSite, ...] = ()
    execution_scope: Literal["module", "deferred"] = "module"

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        return {
            "declaration": self.declaration.to_dict(root),
            "owner": self.owner.to_dict(root),
            "application": self.application.to_dict(root) if self.application else None,
            "include_chain": [site.to_dict(root) for site in self.include_chain],
            "execution_scope": self.execution_scope,
        }


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    location: SourceLocation
    severity: Literal["warning", "error"] = "warning"

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "location": self.location.to_dict(root),
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class DependencyEvidence:
    """A route-local declaration, not proof of callable resolution or access control."""

    kind: Literal["Depends", "Security"]
    target: str | None
    location: SourceLocation
    declaration_level: Literal["parameter-default", "parameter-annotation", "decorator"]
    parameter: str | None = None
    resolution: Literal["reference", "unresolved"] = "reference"
    scopes: tuple[str, ...] | None = None
    unresolved_reasons: tuple[str, ...] = ()

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "location": self.location.to_dict(root),
            "declaration_level": self.declaration_level,
            "parameter": self.parameter,
            "resolution": self.resolution,
            "scopes": list(self.scopes) if self.scopes is not None else None,
            "unresolved_reasons": list(self.unresolved_reasons),
        }


@dataclass(frozen=True, slots=True)
class Route:
    """A FastAPI-style route found in Python source."""

    path: str
    methods: tuple[str, ...]
    function: str
    file: Path
    line: int
    registration: RegistrationEvidence | None = None
    dependencies: tuple[DependencyEvidence, ...] = ()

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        file_path = _source_path(self.file, root)
        data = {
            "path": self.path,
            "methods": list(self.methods),
            "function": self.function,
            "file": str(file_path),
            "line": self.line,
        }
        registration = self.registration.to_dict(root) if self.registration else None
        registration_id = None
        if registration is not None:
            # Identity describes this source registration, not a runtime object or approval token.
            identity = {**data, "file": file_path.as_posix(), "registration": registration}
            canonical = json.dumps(
                identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            registration_id = "route-" + sha256(canonical.encode("utf-8")).hexdigest()
        data["registration_id"] = registration_id
        data["registration"] = registration
        # Keep the 1.0 identity contract: dependency edits do not change a registration ID.
        data["dependencies"] = [dependency.to_dict(root) for dependency in self.dependencies]
        return data


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Framework-neutral result returned by the analysis core."""

    root: Path
    python_files: int
    routes: tuple[Route, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)
    codex_status: str = "disabled"
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def analysis_status(self) -> Literal["bounded", "partial"]:
        return "partial" if self.parse_errors or self.diagnostics else "bounded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "python_files": self.python_files,
            "route_count": len(self.routes),
            "routes": [route.to_dict(self.root) for route in self.routes],
            "parse_errors": list(self.parse_errors),
            "codex_status": self.codex_status,
            "schema_version": REPORT_SCHEMA_VERSION,
            "analysis_status": self.analysis_status,
            "diagnostics": [diagnostic.to_dict(self.root) for diagnostic in self.diagnostics],
        }
