"""Pure selected 0.153.0 response checks, never a live session or entitlement test.

This conservative subset may refuse protocol-valid optional metadata. Inputs are
caller-supplied declarations; matching them proves neither authentication, fresh root
sessions, server behavior, model access nor effective provider computation. No files,
accounts, processes, configuration, clocks or providers are accessed here.
"""

from __future__ import annotations

import re

from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts import evaluation_trial_plan as planner

SemanticError = common.SemanticError
Boundary = common.Boundary
require = common.require
MAX_PAGES = 10
MAX_MODELS_PER_PAGE = 100
MAX_MODELS = 1000
MAX_EFFORTS = 64
MAX_TEXT = 4096
VERSION = "0.153.0"
PLAN_TYPES = frozenset(
    (
        "free",
        "go",
        "plus",
        "pro",
        "prolite",
        "team",
        "self_serve_business_prolite",
        "self_serve_business_usage_based",
        "business",
        "ent26",
        "enterprise_cbp_automation",
        "enterprise_cbp_usage_based",
        "enterprise",
        "edu",
        "edu_plus",
        "edu_pro",
        "unknown",
    )
)


def _object(value: object, required: set[str], optional: set[str] | None = None) -> dict:
    require(type(value) is dict, "invalid-object")
    require(required <= value.keys(), "missing-selected-fields")
    require(value.keys() <= required | (optional or set()), "unsupported-fields")
    return value


def _text(value: object, *, nonempty: bool = False, maximum: int = MAX_TEXT) -> None:
    require(
        type(value) is str and int(nonempty) <= len(value) <= maximum,
        "invalid-text",
    )


def _integer(value: object) -> None:
    require(type(value) is int and 0 <= value < 2**63, "invalid-integer")


def _nulls(value: dict, fields: set[str]) -> None:
    require(all(value.get(field) is None for field in fields), "unsupported-context")


def _summary(check: str, **counts: object) -> dict:
    return {
        "kind": "offline-selected-session-semantics",
        "check": check,
        "supplied_fields_match": True,
        "semantic_scope": "selected-caller-supplied-fields-not-full-schema",
        **counts,
        **common.limitations(),
    }


def _configuration(configuration: planner.TrialConfig) -> None:
    require(type(configuration) is planner.TrialConfig, "invalid-configuration")
    try:
        configuration.__post_init__()
    except (planner.TrialPlanError, AttributeError, TypeError):
        raise SemanticError("invalid-configuration") from None


def _boundary(boundary: Boundary) -> None:
    require(type(boundary) is Boundary, "invalid-boundary")
    boundary.validate()


def check_initialize(result: object) -> dict:
    value = _object(
        common.checked(result), {"userAgent", "codexHome", "platformFamily", "platformOs"}
    )
    for field in value:
        _text(value[field], nonempty=True)
    require(value["codexHome"].startswith("/"), "unsupported-codex-home")
    require(value["platformFamily"] == "unix", "unsupported-platform")
    require(value["platformOs"] in ("linux", "macos"), "unsupported-platform")
    require(
        re.search(rf"/{re.escape(VERSION)}(?:\s|$)", value["userAgent"]) is not None,
        "version-mismatch",
    )
    return _summary("initialize")


def check_remote(result: object) -> dict:
    value = _object(
        common.checked(result), {"installationId", "serverName", "status"}, {"environmentId"}
    )
    _text(value["installationId"], nonempty=True)
    _text(value["serverName"], nonempty=True)
    require(value["status"] == "disabled", "remote-not-disabled")
    # A non-null associated environment is outside this narrow disabled candidate.
    _nulls(value, {"environmentId"})
    return _summary("remote")


def check_account(result: object) -> dict:
    value = _object(common.checked(result), {"account", "requiresOpenaiAuth"})
    require(type(value["requiresOpenaiAuth"]) is bool, "invalid-auth-requirement")
    account = _object(value["account"], {"type", "email", "planType"})
    require(account["type"] == "chatgpt", "unsupported-account-declaration")
    if account["email"] is not None:
        _text(account["email"], maximum=512)
    require(
        type(account["planType"]) is str and account["planType"] in PLAN_TYPES,
        "unsupported-plan-declaration",
    )
    # requiresOpenaiAuth is a provider requirement, not an authenticated-login flag.
    return _summary("account")


def _model(value: object) -> tuple[str, str, tuple[str, ...]]:
    required = {
        "id",
        "model",
        "displayName",
        "description",
        "hidden",
        "isDefault",
        "defaultReasoningEffort",
        "supportedReasoningEfforts",
    }
    nullable = {
        "availabilityNux",
        "defaultServiceTier",
        "modelSpecialty",
        "multiAgentVersion",
        "upgrade",
        "upgradeInfo",
    }
    model = _object(
        value,
        required,
        nullable
        | {"additionalSpeedTiers", "inputModalities", "serviceTiers", "supportsPersonality"},
    )
    for field in ("id", "model", "displayName", "defaultReasoningEffort"):
        _text(model[field], nonempty=True, maximum=128)
    _text(model["description"])
    require(type(model["hidden"]) is bool and model["hidden"] is False, "hidden-model")
    require(type(model["isDefault"]) is bool, "invalid-model-metadata")
    efforts = model["supportedReasoningEfforts"]
    require(type(efforts) is list and 1 <= len(efforts) <= MAX_EFFORTS, "invalid-effort-options")
    labels = []
    for option in efforts:
        option = _object(option, {"reasoningEffort", "description"})
        _text(option["reasoningEffort"], nonempty=True, maximum=128)
        _text(option["description"])
        require(option["reasoningEffort"] not in labels, "duplicate-effort-option")
        labels.append(option["reasoningEffort"])
    require(model["defaultReasoningEffort"] in labels, "invalid-effort-default")
    # Optional complex metadata is deliberately supported only when unset. This is
    # narrower than the generated schema, not evidence that a real catalog omits it.
    _nulls(model, nullable)
    if "supportsPersonality" in model:
        require(type(model["supportsPersonality"]) is bool, "invalid-model-metadata")
    for field in ("additionalSpeedTiers", "serviceTiers"):
        if field in model:
            require(type(model[field]) is list and model[field] == [], "unsupported-model-metadata")
    if "inputModalities" in model:
        modalities = model["inputModalities"]
        require(type(modalities) is list, "invalid-model-metadata")
        require(
            all(type(item) is str and item in ("text", "image", "audio") for item in modalities)
            and len(modalities) == len(set(modalities))
            and "text" in modalities,
            "invalid-model-metadata",
        )
    return model["id"], model["model"], tuple(labels)


def check_catalog(pages: object, configuration: planner.TrialConfig) -> dict:
    _configuration(configuration)
    values = common.checked(pages, max_bytes=common.MAX_TOTAL_BYTES)
    require(type(values) is list and 1 <= len(values) <= MAX_PAGES, "invalid-catalog-pages")
    ids: set[str] = set()
    names: set[str] = set()
    cursors: set[str] = set()
    matches = 0
    for index, raw_page in enumerate(values):
        page = _object(common.checked(raw_page), {"data", "nextCursor"})
        data = page["data"]
        require(type(data) is list and len(data) <= MAX_MODELS_PER_PAGE, "invalid-catalog-page")
        cursor = page["nextCursor"]
        if index < len(values) - 1:
            _text(cursor, nonempty=True, maximum=512)
            require(cursor not in cursors, "catalog-cursor-cycle")
            cursors.add(cursor)
        else:
            require(cursor is None, "incomplete-catalog")
        for raw_model in data:
            identity, name, efforts = _model(raw_model)
            require(identity not in ids and name not in names, "duplicate-model")
            ids.add(identity)
            names.add(name)
            require(len(ids) <= MAX_MODELS, "too-many-models")
            if name == configuration.model:
                require(configuration.effort in efforts, "effort-not-advertised")
                matches += 1
    require(matches == 1, "model-not-advertised")
    return _summary("catalog", pages_count=len(values), models_count=len(ids))


def _sandbox(value: object) -> None:
    sandbox = _object(value, {"type", "networkAccess"})
    require(sandbox["type"] == "readOnly" and sandbox["networkAccess"] is False, "sandbox-mismatch")


def _negotiated(value: dict, boundary: Boundary, *, effort_key: str) -> None:
    expected = {
        "model": boundary.configuration.model,
        "modelProvider": "openai",
        "cwd": boundary.cwd,
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        effort_key: boundary.configuration.effort,
    }
    require(
        all(type(value.get(key)) is str and value[key] == item for key, item in expected.items()),
        "boundary-mismatch",
    )


def _mode(value: dict) -> None:
    if "multiAgentMode" in value:
        require(value["multiAgentMode"] == "explicitRequestOnly", "unsupported-multi-agent-mode")


def check_thread_start(result: object, boundary: Boundary) -> dict:
    _boundary(boundary)
    value = _object(
        common.checked(result),
        {
            "thread",
            "model",
            "modelProvider",
            "cwd",
            "approvalPolicy",
            "approvalsReviewer",
            "sandbox",
            "reasoningEffort",
            "instructionSources",
            "runtimeWorkspaceRoots",
        },
        {"activePermissionProfile", "multiAgentMode", "serviceTier"},
    )
    _negotiated(value, boundary, effort_key="reasoningEffort")
    _sandbox(value["sandbox"])
    for field in ("instructionSources", "runtimeWorkspaceRoots"):
        require(type(value[field]) is list and value[field] == [], "unexpected-thread-context")
    _nulls(value, {"activePermissionProfile", "serviceTier"})
    _mode(value)
    optional_null = {
        "agentNickname",
        "agentRole",
        "extra",
        "forkedFromId",
        "gitInfo",
        "name",
        "parentThreadId",
        "path",
        "recencyAt",
        "section",
        "sectionEnteredAt",
        "threadSource",
    }
    thread = _object(
        value["thread"],
        {
            "cliVersion",
            "createdAt",
            "cwd",
            "ephemeral",
            "id",
            "modelProvider",
            "preview",
            "projectId",
            "sessionId",
            "source",
            "status",
            "turns",
            "updatedAt",
        },
        optional_null | {"canAcceptDirectInput", "historyMode", "model", "reasoningEffort"},
    )
    require(common.identifier(thread["id"]) == boundary.thread_id, "thread-id-mismatch")
    common.identifier(thread["sessionId"])
    require(thread["cliVersion"] == VERSION, "version-mismatch")
    require(
        thread["cwd"] == boundary.cwd and thread["modelProvider"] == "openai", "boundary-mismatch"
    )
    require(thread["ephemeral"] is True, "thread-not-ephemeral")
    require(thread["source"] == "appServer", "unsupported-session-source")
    require(thread["preview"] == "" and thread["projectId"] is None, "unexpected-thread-context")
    require(type(thread["turns"]) is list and thread["turns"] == [], "unexpected-thread-context")
    require(thread["status"] == {"type": "idle"}, "unexpected-thread-status")
    _integer(thread["createdAt"])
    _integer(thread["updatedAt"])
    require(thread["updatedAt"] >= thread["createdAt"], "invalid-thread-timestamps")
    _nulls(thread, optional_null)
    if "canAcceptDirectInput" in thread:
        require(thread["canAcceptDirectInput"] is True, "unsupported-input-capability")
    if "historyMode" in thread:
        require(thread["historyMode"] == "legacy", "unsupported-history-mode")
    for field, expected in (
        ("model", boundary.configuration.model),
        ("reasoningEffort", boundary.configuration.effort),
    ):
        if field in thread:
            require(thread[field] == expected, "boundary-mismatch")
    return _summary("thread-start")


def check_settings(params: object, boundary: Boundary) -> dict:
    _boundary(boundary)
    value = _object(common.checked(params), {"threadId", "threadSettings"})
    require(common.identifier(value["threadId"]) == boundary.thread_id, "thread-id-mismatch")
    optional_null = {"activePermissionProfile", "personality", "serviceTier", "summary"}
    settings = _object(
        value["threadSettings"],
        {
            "model",
            "modelProvider",
            "cwd",
            "approvalPolicy",
            "approvalsReviewer",
            "effort",
            "sandboxPolicy",
            "collaborationMode",
        },
        optional_null | {"multiAgentMode"},
    )
    _negotiated(settings, boundary, effort_key="effort")
    _sandbox(settings["sandboxPolicy"])
    mode = _object(settings["collaborationMode"], {"mode", "settings"})
    require(mode["mode"] == "default", "collaboration-mismatch")
    fields = _object(mode["settings"], {"model", "reasoning_effort", "developer_instructions"})
    require(
        fields["model"] == boundary.configuration.model
        and fields["reasoning_effort"] == boundary.configuration.effort
        and fields["developer_instructions"] == codec.INSTRUCTIONS,
        "collaboration-mismatch",
    )
    _nulls(settings, optional_null)
    _mode(settings)
    return _summary("settings")
