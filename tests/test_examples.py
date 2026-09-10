import builtins
import json
from pathlib import Path

import pytest

from authzest.runner import ScanRunner

REPOSITORY = Path(__file__).resolve().parents[1]
EXAMPLE = REPOSITORY / "examples" / "fastapi_inventory"
EXPECTED = Path(__file__).parent / "fixtures" / "fastapi_inventory.json"


def test_owned_example_matches_the_documented_inventory_without_importing_the_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def reject_target_import(name: str, *args: object, **kwargs: object) -> object:
        assert name.split(".")[0] not in {"fastapi", "routers", "examples", "app"}, (
            f"Inventory must not import its target or its framework: {name}"
        )
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_target_import)

    report = ScanRunner().run(EXAMPLE)
    payload = report.to_dict()

    assert payload.pop("root") == str(EXAMPLE.resolve())
    for route in payload["routes"]:
        route["file"] = Path(route["file"]).as_posix()
    assert payload == json.loads(EXPECTED.read_text(encoding="utf-8"))
