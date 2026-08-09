"""Phase + gate state machine for the ppt-design-flow skill.

This module owns ``state.json`` per session and is the only source of truth for
phase progression. Both ``scripts/stage.py`` and ``assets/canvas/build.py``
delegate every transition / pre-flight check to the functions defined here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from canvas_protocol import SKILL_NAME, _atomic_write_json, validate_session_id


STATE_VERSION = 1
STATE_FILENAME = "state.json"

PHASE_ORDER: tuple[str, ...] = (
    "intake",
    "content-basis",
    "style",
    "planning",
    "generation",
    "review",
    "revision",
    "done",
)

# Gates exit each phase. The order inside the list dictates legal pass order.
GATE_FOR_PHASE: dict[str, tuple[str, ...]] = {
    "intake": ("needs_confirmed",),
    "content-basis": (),
    "style": ("style_locked", "style_breakdown_confirmed"),
    "planning": ("pre_generation_confirmed",),
    "generation": (),
    "review": ("review_approved",),
    "revision": (),
    "done": (),
}

ALL_GATES: tuple[str, ...] = tuple(g for gates in GATE_FOR_PHASE.values() for g in gates)
GATE_TO_PHASE: dict[str, str] = {g: p for p, gates in GATE_FOR_PHASE.items() for g in gates}

# Entry preconditions for each phase: gates that MUST be in ``gates_passed``.
ENTRY_REQUIRES: dict[str, tuple[str, ...]] = {
    "intake": (),
    "content-basis": ("needs_confirmed",),
    "style": ("needs_confirmed",),
    "planning": ("style_locked", "style_breakdown_confirmed"),
    "generation": ("pre_generation_confirmed",),
    "review": ("pre_generation_confirmed",),
    "revision": ("review_approved",),
    "done": ("review_approved",),
}

FLAG_DEFAULTS: dict[str, Any] = {
    "content_basis_ready": False,
    "pages_ready": False,
    "preview_mode": None,
    "candidate_mode": None,
    "fast_mode": False,
    "output_formats": [],
    "revision_active": False,
    "revision_id": None,
    "revision_pages": [],
}
FLAG_WHITELIST: frozenset[str] = frozenset(FLAG_DEFAULTS)
FLAG_ORDER: tuple[str, ...] = (
    "content_basis_ready",
    "pages_ready",
    "preview_mode",
    "candidate_mode",
    "fast_mode",
    "output_formats",
    "revision_active",
    "revision_id",
    "revision_pages",
)

# Phase scope for flag reset: flags scoped to a phase get cleared when the user
# resets to (or before) that phase.
FLAG_PHASE_SCOPE: dict[str, str] = {
    "preview_mode": "style",
    "candidate_mode": "generation",
    "content_basis_ready": "content-basis",
    "pages_ready": "generation",
    "revision_active": "revision",
    "revision_id": "revision",
    "revision_pages": "revision",
}

FLAG_ENUMS: dict[str, frozenset[str]] = {
    "preview_mode": frozenset({"svg", "imagegen"}),
    "candidate_mode": frozenset({"single", "multi"}),
}
FLAG_BOOLS: frozenset[str] = frozenset({"content_basis_ready", "pages_ready", "fast_mode", "revision_active"})
OUTPUT_FORMATS: frozenset[str] = frozenset({"pptx", "html"})
SLIDE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

PHASE_FILES: dict[str, str] = {
    "intake": "phases/10-intake.md",
    "content-basis": "phases/20-content-basis.md",
    "style": "phases/30-style.md",
    "planning": "phases/40-planning.md",
    "generation": "phases/50-generation.md",
    "review": "phases/60-review.md",
    "revision": "phases/60-review.md",
    "done": "phases/60-review.md",
}


@dataclass(frozen=True)
class FlagContains:
    key: str
    value: str


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    state_file: Path
    current_phase: str
    gates_passed: list[str]
    flags: dict[str, Any]
    created_at: str
    updated_at: str
    is_complete: bool
    next_gate: str | None
    next_action: str
    phase_file: str
    sort_time: float
    sort_time_source: str


@dataclass(frozen=True)
class InvalidSessionSummary:
    session_id: str
    state_file: Path
    error: str
    sort_time: float


@dataclass(frozen=True)
class SessionDiscovery:
    sessions: list[SessionSummary]
    invalid: list[InvalidSessionSummary]


def default_flags() -> dict[str, Any]:
    return {key: (list(value) if isinstance(value, list) else value) for key, value in FLAG_DEFAULTS.items()}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StageError(Exception):
    """Base class for phase-machine errors. Subclasses define a stderr renderer."""

    exit_code = 3

    def render(self) -> str:
        return str(self)


class StagePreflightError(StageError):
    """Raised by ``require()`` when builder pre-flight constraints fail."""

    exit_code = 2

    def __init__(
        self,
        *,
        phase_label: str,
        current_phase: str,
        gates_passed: list[str],
        required_gates: list[str],
        missing: list[str],
        next_action: str,
    ) -> None:
        self.phase_label = phase_label
        self.current_phase = current_phase
        self.gates_passed = list(gates_passed)
        self.required_gates = list(required_gates)
        self.missing = list(missing)
        self.next_action_text = next_action
        super().__init__(self.render())

    def render(self) -> str:
        label_suffix = "" if self.phase_label.endswith("deck") else " canvas"
        lines = [
            f"[stage] cannot build {self.phase_label}{label_suffix}: missing precondition",
            f"  current_phase   : {self.current_phase}",
            f"  gates_passed    : [{', '.join(self.gates_passed)}]",
            f"  required_gates  : [{', '.join(self.required_gates)}]",
            f"  missing         : [{', '.join(self.missing)}]",
            "  next_action     : obtain user confirmation, then run:",
            f"                    {self.next_action_text}",
        ]
        return "\n".join(lines)


class InvalidTransitionError(StageError):
    """Raised by ``pass_gate`` / ``enter_phase`` / ``set_flag`` / ``reset``."""

    exit_code = 3

    def __init__(self, message: str, details: dict[str, str] | None = None) -> None:
        self.detail_lines = details or {}
        self.headline = message
        super().__init__(self.render())

    def render(self) -> str:
        lines = [f"[stage] {self.headline}"]
        for key, value in self.detail_lines.items():
            lines.append(f"  {key:<16}: {value}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dataclass + persistence
# ---------------------------------------------------------------------------


@dataclass
class State:
    session_id: str
    workspace_dir: Path
    current_phase: str = "intake"
    gates_passed: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=default_flags)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: int = STATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "skill": SKILL_NAME,
            "session_id": self.session_id,
            "current_phase": self.current_phase,
            "gates_passed": list(self.gates_passed),
            "flags": dict(self.flags),
            "history": list(self.history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _session_dir(workspace_dir: Path, session_id: str) -> Path:
    validate_session_id(session_id)
    return Path(workspace_dir).resolve() / ".aileron" / "canvases" / SKILL_NAME / session_id


def state_path(workspace_dir: Path, session_id: str) -> Path:
    return _session_dir(workspace_dir, session_id) / STATE_FILENAME


def _sessions_root(workspace_dir: Path) -> Path:
    return Path(workspace_dir).resolve() / ".aileron" / "canvases" / SKILL_NAME


def init(workspace_dir: Path, session_id: str) -> State:
    path = state_path(workspace_dir, session_id)
    if path.exists():
        raise InvalidTransitionError(
            f"state.json already exists for session '{session_id}'",
            {"path": str(path)},
        )
    now = _now()
    state = State(
        session_id=session_id,
        workspace_dir=Path(workspace_dir).resolve(),
        current_phase="intake",
        gates_passed=[],
        flags=default_flags(),
        history=[{"at": now, "event": "phase_enter", "phase": "intake"}],
        created_at=now,
        updated_at=now,
    )
    save(state)
    return state


def load(workspace_dir: Path, session_id: str) -> State:
    path = state_path(workspace_dir, session_id)
    if not path.exists():
        raise InvalidTransitionError(
            f"state.json not found for session '{session_id}'",
            {"path": str(path), "hint": "run: python3 scripts/stage.py init --session-id <YYYY-MM-DD-title-slug>"},
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    flags = default_flags()
    flags.update(data.get("flags") or {})
    return State(
        session_id=data["session_id"],
        workspace_dir=Path(workspace_dir).resolve(),
        current_phase=data["current_phase"],
        gates_passed=list(data.get("gates_passed", [])),
        flags=flags,
        history=list(data.get("history", [])),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        version=int(data.get("version", STATE_VERSION)),
    )


def save(state: State) -> None:
    state.updated_at = _now()
    path = state_path(state.workspace_dir, state.session_id)
    _atomic_write_json(path, state.to_dict())


def _append_history(state: State, event: str, **payload: Any) -> None:
    entry: dict[str, Any] = {"at": _now(), "event": event}
    entry.update(payload)
    state.history.append(entry)


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


def _phase_index(phase: str) -> int:
    try:
        return PHASE_ORDER.index(phase)
    except ValueError as exc:
        raise InvalidTransitionError(
            f"unknown phase '{phase}'",
            {"allowed": ", ".join(PHASE_ORDER)},
        ) from exc


def _next_gate_for(state: State) -> str | None:
    gates = GATE_FOR_PHASE.get(state.current_phase, ())
    for gate in gates:
        if gate not in state.gates_passed:
            return gate
    return None


def pass_gate(state: State, gate_id: str) -> State:
    if gate_id not in ALL_GATES:
        raise InvalidTransitionError(
            f"unknown gate '{gate_id}'",
            {"allowed": ", ".join(ALL_GATES)},
        )
    if gate_id in state.gates_passed:
        raise InvalidTransitionError(
            f"gate '{gate_id}' has already been passed",
            {"current_phase": state.current_phase},
        )
    expected = _next_gate_for(state)
    if expected is None:
        raise InvalidTransitionError(
            f"phase '{state.current_phase}' has no remaining gates",
            {"hint": "advance with: python3 scripts/stage.py enter <next-phase>"},
        )
    if gate_id != expected:
        raise InvalidTransitionError(
            f"cannot pass gate '{gate_id}'",
            {
                "current_phase": state.current_phase,
                "gates_passed": f"[{', '.join(state.gates_passed)}]",
                "expected_gate": f"{expected}   (next legal gate for phase '{state.current_phase}')",
            },
        )
    state.gates_passed.append(gate_id)
    _append_history(state, "gate_pass", gate=gate_id)
    save(state)
    return state


def enter_phase(state: State, phase_id: str) -> State:
    target_index = _phase_index(phase_id)
    current_index = _phase_index(state.current_phase)
    if target_index <= current_index:
        raise InvalidTransitionError(
            f"cannot re-enter phase '{phase_id}' from '{state.current_phase}'",
            {"hint": "use 'reset --from <phase>' to move backward"},
        )
    required = ENTRY_REQUIRES.get(phase_id, ())
    missing = [g for g in required if g not in state.gates_passed]
    if missing:
        raise InvalidTransitionError(
            f"cannot enter phase '{phase_id}': missing gate(s) '{', '.join(missing)}'",
            {
                "current_phase": state.current_phase,
                "gates_passed": f"[{', '.join(state.gates_passed)}]",
                "missing": f"[{', '.join(missing)}]",
            },
        )
    state.current_phase = phase_id
    _append_history(state, "phase_enter", phase=phase_id)
    save(state)
    return state


def set_flag(state: State, key: str, value: Any) -> State:
    if key not in FLAG_WHITELIST:
        raise InvalidTransitionError(
            f"unknown flag '{key}'; allowed: [{', '.join(FLAG_ORDER)}]"
        )
    parsed = _parse_flag_value(key, value)
    _validate_flag_scope(state, key, parsed)
    state.flags[key] = parsed
    _append_history(state, "flag_set", key=key, value=parsed)
    save(state)
    return state


def _validate_flag_scope(state: State, key: str, parsed: Any) -> None:
    if key == "fast_mode" and parsed is True and state.current_phase != "intake":
        raise InvalidTransitionError("fast_mode can only be enabled during intake")
    if key == "output_formats" and "review_approved" not in state.gates_passed:
        raise InvalidTransitionError("output_formats can only be set after review_approved")
    if key in {"revision_active", "revision_id", "revision_pages"} and state.current_phase != "revision":
        raise InvalidTransitionError("revision flags can only be set during revision")


def _parse_flag_value(key: str, value: Any) -> Any:
    if key in FLAG_BOOLS:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text == "true":
            return True
        if text == "false":
            return False
        raise InvalidTransitionError(
            f"flag '{key}' must be one of {{true, false}}",
            {"received": str(value)},
        )
    if key in FLAG_ENUMS:
        text = str(value).strip()
        allowed = FLAG_ENUMS[key]
        if text in allowed:
            return text
        raise InvalidTransitionError(
            f"flag '{key}' must be one of {{{', '.join(sorted(allowed))}}}",
            {"received": text},
        )
    if key == "output_formats":
        if isinstance(value, list):
            parsed = value
        else:
            try:
                parsed = json.loads(str(value))
            except json.JSONDecodeError as exc:
                raise InvalidTransitionError(
                    "flag 'output_formats' must be a JSON list",
                    {"received": str(value)},
                ) from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise InvalidTransitionError(
                "flag 'output_formats' must be a JSON list of strings",
                {"received": str(value)},
            )
        invalid = [item for item in parsed if item not in OUTPUT_FORMATS]
        if invalid:
            raise InvalidTransitionError(
                "output_formats elements must be one of {pptx, html}",
                {"received": ", ".join(invalid)},
            )
        return parsed
    if key == "revision_pages":
        if isinstance(value, list):
            parsed = value
        else:
            try:
                parsed = json.loads(str(value))
            except json.JSONDecodeError as exc:
                raise InvalidTransitionError(
                    "flag 'revision_pages' must be a JSON list",
                    {"received": str(value)},
                ) from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise InvalidTransitionError(
                "flag 'revision_pages' must be a JSON list of strings",
                {"received": str(value)},
            )
        invalid = [item for item in parsed if not SLIDE_ID_RE.fullmatch(item)]
        if invalid:
            raise InvalidTransitionError(
                "revision_pages elements must match ^[A-Za-z0-9_-]{1,64}$",
                {"received": ", ".join(invalid)},
            )
        return parsed
    if key == "revision_id":
        if value in {None, "", "null"}:
            return None
        text = str(value).strip()
        if not re.fullmatch(r"revision-\d{3}", text):
            raise InvalidTransitionError(
                "revision_id must match revision-###",
                {"received": text},
            )
        return text
    return value


def reset(state: State, from_phase: str) -> State:
    target_index = _phase_index(from_phase)
    current_index = _phase_index(state.current_phase)
    if target_index > current_index:
        raise InvalidTransitionError(
            f"reset cannot move forward ({state.current_phase} → {from_phase})"
        )
    # Truncate gates whose owning phase is at or after the target phase.
    kept: list[str] = []
    for gate in state.gates_passed:
        gate_phase = GATE_TO_PHASE.get(gate)
        if gate_phase is None:
            continue
        if _phase_index(gate_phase) < target_index:
            kept.append(gate)
    state.gates_passed = kept
    # Reset flags scoped to the target phase or later.
    for flag_key, scope_phase in FLAG_PHASE_SCOPE.items():
        if _phase_index(scope_phase) >= target_index:
            state.flags[flag_key] = FLAG_DEFAULTS[flag_key]
    state.flags["output_formats"] = []
    if from_phase in {"style", "planning", "generation", "review"}:
        state.flags["fast_mode"] = False
    state.current_phase = from_phase
    _append_history(state, "phase_reset", phase=from_phase)
    save(state)
    return state


def revise(state: State, *, pages: list[str] | None = None, reason: str | None = None) -> State:
    """Enter post-completion revision mode for an approved deck session."""

    if "review_approved" not in state.gates_passed:
        raise InvalidTransitionError(
            "cannot enter revision: missing review_approved",
            {
                "current_phase": state.current_phase,
                "gates_passed": f"[{', '.join(state.gates_passed)}]",
            },
        )
    if state.current_phase == "revision" or state.flags.get("revision_active") is True:
        raise InvalidTransitionError(
            "cannot enter revision: revision is already active",
            {"revision_id": str(state.flags.get("revision_id") or "-")},
        )
    normalized_pages = _normalize_revision_pages(pages or [])
    _validate_revision_pages(state, normalized_pages)
    revision_id = _next_revision_id(state)
    request = {
        "version": 1,
        "skill": SKILL_NAME,
        "session_id": state.session_id,
        "revision_id": revision_id,
        "pages": normalized_pages,
        "reason": reason or "Post-completion page revision",
        "status": "active",
        "created_at": _now(),
        "updated_at": _now(),
    }
    _write_revision_request(state, revision_id, request)
    state.current_phase = "revision"
    state.flags["revision_active"] = True
    state.flags["revision_id"] = revision_id
    state.flags["revision_pages"] = normalized_pages
    _append_history(state, "revision_enter", revision_id=revision_id, pages=normalized_pages)
    save(state)
    return state


def complete_revision(state: State) -> State:
    """Complete an active revision round and return the session to done."""

    if state.current_phase != "revision":
        raise InvalidTransitionError(
            "cannot complete revision: session is not in revision",
            {"current_phase": state.current_phase},
        )
    revision_id = state.flags.get("revision_id")
    if isinstance(revision_id, str):
        request_path = _revision_dir(state, revision_id) / "request.json"
        if request_path.exists():
            data = json.loads(request_path.read_text(encoding="utf-8"))
            data["status"] = "complete"
            data["updated_at"] = _now()
            _atomic_write_json(request_path, data)
    state.current_phase = "done"
    state.flags["revision_active"] = False
    state.flags["revision_id"] = None
    state.flags["revision_pages"] = []
    _append_history(state, "revision_complete", revision_id=revision_id or "-")
    save(state)
    return state


def _normalize_revision_pages(pages: list[str]) -> list[str]:
    normalized: list[str] = []
    for page in pages:
        text = str(page).strip()
        if not text:
            continue
        if not SLIDE_ID_RE.fullmatch(text):
            raise InvalidTransitionError(
                "revision page ids must match ^[A-Za-z0-9_-]{1,64}$",
                {"received": text},
            )
        if text not in normalized:
            normalized.append(text)
    return normalized


def _final_pages_manifest_path(state: State) -> Path:
    return _session_dir(state.workspace_dir, state.session_id) / "generation" / "final-pages.json"


def current_final_page_ids(state: State) -> set[str]:
    path = _final_pages_manifest_path(state)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = data.get("pages", []) if isinstance(data, dict) else []
    result: set[str] = set()
    for page in pages:
        if isinstance(page, dict) and isinstance(page.get("slide_id"), str):
            result.add(page["slide_id"])
    return result


def _validate_revision_pages(state: State, pages: list[str]) -> None:
    if not pages:
        return
    available = current_final_page_ids(state)
    missing = [page for page in pages if page not in available]
    if missing:
        raise InvalidTransitionError(
            "unknown revision page",
            {
                "missing": ", ".join(missing),
                "available": ", ".join(sorted(available)) or "-",
            },
        )


def _next_revision_id(state: State) -> str:
    root = _session_dir(state.workspace_dir, state.session_id) / "revisions"
    highest = 0
    if root.exists():
        for path in root.iterdir():
            match = re.fullmatch(r"revision-(\d{3})", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"revision-{highest + 1:03d}"


def _revision_dir(state: State, revision_id: str) -> Path:
    return _session_dir(state.workspace_dir, state.session_id) / "revisions" / revision_id


def _write_revision_request(state: State, revision_id: str, request: dict[str, Any]) -> None:
    _atomic_write_json(_revision_dir(state, revision_id) / "request.json", request)


# ---------------------------------------------------------------------------
# Builder pre-flight
# ---------------------------------------------------------------------------


def require(
    workspace_dir: Path,
    session_id: str,
    *,
    phase_label: str,
    phases: tuple[str, ...] | None = None,
    gates: tuple[str, ...] = (),
    flags: dict[str, Any] | None = None,
    flag_contains: tuple[FlagContains, ...] = (),
    next_action: str,
) -> State:
    """Raise ``StagePreflightError`` when a builder pre-flight constraint fails.

    ``phases`` is a tuple of acceptable ``current_phase`` values. ``gates`` is
    the set of gates that must already be passed. ``flags`` is a key-to-expected
    mapping. ``phase_label`` and ``next_action`` are embedded into the rendered
    error message for LLM-readable guidance.
    """
    state = load(workspace_dir, session_id)
    flags_expected = flags or {}

    missing: list[str] = []
    if phases and state.current_phase not in phases:
        missing.append(f"current_phase∈{{{', '.join(phases)}}}")
    for gate in gates:
        if gate not in state.gates_passed:
            missing.append(gate)
    for key, expected in flags_expected.items():
        actual = state.flags.get(key)
        if actual != expected:
            if isinstance(expected, bool):
                missing.append(f"{key}={'true' if expected else 'false'}")
            else:
                missing.append(f"{key}={expected}")
    for expected in flag_contains:
        actual = state.flags.get(expected.key)
        if not isinstance(actual, list) or expected.value not in actual:
            missing.append(f"{expected.key} contains {expected.value}")

    if missing:
        raise StagePreflightError(
            phase_label=phase_label,
            current_phase=state.current_phase,
            gates_passed=state.gates_passed,
            required_gates=list(gates),
            missing=missing,
            next_action=next_action,
        )
    return state


# ---------------------------------------------------------------------------
# Session discovery / resume helpers
# ---------------------------------------------------------------------------


def _parse_sort_time(value: str, path: Path) -> tuple[float, str]:
    if value:
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp(), "updated_at"
        except ValueError:
            pass
    try:
        return path.stat().st_mtime, "mtime"
    except OSError:
        return 0.0, "unknown"


def _next_phase_for(phase: str) -> str | None:
    idx = _phase_index(phase)
    if idx < len(PHASE_ORDER) - 1:
        return PHASE_ORDER[idx + 1]
    return None


def summarize_state(state: State, state_file: Path | None = None) -> SessionSummary:
    """Return an immutable, display-oriented summary without mutating state."""

    next_gate = _next_gate_for(state)
    next_phase = _next_phase_for(state.current_phase) if next_gate is None else None
    if state.current_phase == "revision":
        next_action = "build revision review"
    else:
        next_action = next_gate or (f"enter '{next_phase}'" if next_phase else "done")
    is_complete = state.current_phase == "done" or (
        "review_approved" in state.gates_passed and state.current_phase != "revision"
    )
    path = state_file or state_path(state.workspace_dir, state.session_id)
    sort_time, sort_source = _parse_sort_time(state.updated_at, path)
    return SessionSummary(
        session_id=state.session_id,
        state_file=path,
        current_phase=state.current_phase,
        gates_passed=list(state.gates_passed),
        flags=dict(state.flags),
        created_at=state.created_at,
        updated_at=state.updated_at,
        is_complete=is_complete,
        next_gate=next_gate,
        next_action=next_action,
        phase_file=PHASE_FILES.get(state.current_phase, "phases/00-overview.md"),
        sort_time=sort_time,
        sort_time_source=sort_source,
    )


def _invalid_summary(path: Path, error: Exception | str) -> InvalidSessionSummary:
    try:
        sort_time = path.stat().st_mtime
    except OSError:
        sort_time = 0.0
    return InvalidSessionSummary(
        session_id=path.parent.name,
        state_file=path,
        error=str(error),
        sort_time=sort_time,
    )


def _load_state_from_path(workspace_dir: Path, path: Path) -> State:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("skill") != SKILL_NAME:
        raise InvalidTransitionError(
            "state file does not belong to ppt-design-flow",
            {"path": str(path)},
        )
    session_id = str(data.get("session_id") or path.parent.name)
    if session_id != path.parent.name:
        raise InvalidTransitionError(
            "state session_id does not match directory name",
            {"session_id": session_id, "directory": path.parent.name},
        )
    validate_session_id(session_id)
    current_phase = data.get("current_phase")
    if current_phase not in PHASE_ORDER:
        raise InvalidTransitionError(
            f"unknown phase '{current_phase}'",
            {"path": str(path)},
        )
    flags = default_flags()
    flags.update(data.get("flags") or {})
    return State(
        session_id=session_id,
        workspace_dir=Path(workspace_dir).resolve(),
        current_phase=current_phase,
        gates_passed=list(data.get("gates_passed", [])),
        flags=flags,
        history=list(data.get("history", [])),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        version=int(data.get("version", STATE_VERSION)),
    )


def discover_sessions(workspace_dir: Path, *, include_completed: bool = False) -> SessionDiscovery:
    root = _sessions_root(workspace_dir)
    sessions: list[SessionSummary] = []
    invalid: list[InvalidSessionSummary] = []
    if not root.exists():
        return SessionDiscovery(sessions=[], invalid=[])

    for path in sorted(root.glob(f"*/{STATE_FILENAME}")):
        try:
            state = _load_state_from_path(workspace_dir, path)
            summary = summarize_state(state, path)
            if include_completed or not summary.is_complete:
                sessions.append(summary)
        except Exception as exc:  # Keep one bad session from hiding the rest.
            invalid.append(_invalid_summary(path, exc))

    sessions.sort(key=lambda item: item.sort_time, reverse=True)
    invalid.sort(key=lambda item: item.sort_time, reverse=True)
    return SessionDiscovery(sessions=sessions, invalid=invalid)


def _format_candidates(
    sessions: list[SessionSummary],
    invalid: list[InvalidSessionSummary] | None = None,
) -> str:
    lines: list[str] = []
    for summary in sessions:
        lines.append(
            f"- {summary.session_id} | phase={summary.current_phase} | "
            f"next={summary.next_action} | updated={summary.updated_at or '-'}"
        )
    for item in invalid or []:
        lines.append(f"- [invalid] {item.session_id} | error={item.error}")
    return "\n".join(lines) if lines else "-"


def resolve_resume_session(workspace_dir: Path, query: str | None = None) -> SessionSummary:
    if query:
        all_result = discover_sessions(workspace_dir, include_completed=True)
        exact = [item for item in all_result.sessions if item.session_id == query]
        exact_invalid = [item for item in all_result.invalid if item.session_id == query]
        if len(exact) == 1:
            return exact[0]
        if exact_invalid:
            raise InvalidTransitionError(
                f"session '{query}' has invalid state",
                {"path": str(exact_invalid[0].state_file), "error": exact_invalid[0].error},
            )

        matches = [item for item in all_result.sessions if query in item.session_id]
        invalid_matches = [item for item in all_result.invalid if query in item.session_id]
        total = len(matches) + len(invalid_matches)
        if total == 1 and matches:
            return matches[0]
        if total == 1 and invalid_matches:
            item = invalid_matches[0]
            raise InvalidTransitionError(
                f"session '{item.session_id}' has invalid state",
                {"path": str(item.state_file), "error": item.error},
            )
        if total > 1:
            raise InvalidTransitionError(
                f"query '{query}' matches multiple sessions",
                {"candidates": "\n" + _format_candidates(matches, invalid_matches)},
            )
        raise InvalidTransitionError(
            f"no session matches query '{query}'",
            {"hint": "run: python3 scripts/stage.py list --all --workspace /workspace"},
        )

    result = discover_sessions(workspace_dir)
    if result.sessions:
        return result.sessions[0]

    all_result = discover_sessions(workspace_dir, include_completed=True)
    if all_result.sessions or all_result.invalid:
        raise InvalidTransitionError(
            "no unfinished ppt-design-flow sessions found",
            {"hint": "run: python3 scripts/stage.py list --all --workspace /workspace"},
        )
    raise InvalidTransitionError(
        "no ppt-design-flow sessions found",
        {"hint": "run: python3 scripts/stage.py init --session-id <YYYY-MM-DD-title-slug> --workspace /workspace"},
    )


def render_session_list(discovery: SessionDiscovery) -> str:
    lines = ["[stage] ppt-design-flow sessions"]
    if not discovery.sessions and not discovery.invalid:
        lines.append("  no sessions found")
        return "\n".join(lines)
    for summary in discovery.sessions:
        lines.append(
            f"  {summary.session_id} | phase={summary.current_phase} | "
            f"next={summary.next_action} | updated={summary.updated_at or '-'} | "
            f"phase_file={summary.phase_file}"
        )
    for item in discovery.invalid:
        lines.append(f"  [invalid] {item.session_id} | path={item.state_file} | error={item.error}")
    return "\n".join(lines)


def render_resume(summary: SessionSummary) -> str:
    lines = [
        "[stage] resume ppt-design-flow session",
        f"  session_id      : {summary.session_id}",
        f"  current_phase   : {summary.current_phase}",
        f"  gates_passed    : [{', '.join(summary.gates_passed)}]",
        f"  next_gate       : {summary.next_gate or '-'}",
        f"  next_action     : {summary.next_action}",
        f"  phase_file      : {summary.phase_file}",
    ]
    if summary.current_phase == "revision":
        lines.append(f"  revision_id     : {summary.flags.get('revision_id') or '-'}")
        pages = summary.flags.get("revision_pages") or []
        lines.append(f"  revision_pages  : [{', '.join(pages)}]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Show helper
# ---------------------------------------------------------------------------


def render_show(state: State) -> str:
    next_gate = _next_gate_for(state)
    next_phase: str | None = None
    if next_gate is None:
        idx = _phase_index(state.current_phase)
        if idx < len(PHASE_ORDER) - 1:
            next_phase = PHASE_ORDER[idx + 1]
    if state.current_phase == "revision":
        next_hint = "build revision review"
    else:
        next_hint = next_gate or (f"enter '{next_phase}'" if next_phase else "done")
    lines = [
        f"  session_id      : {state.session_id}",
        f"  current_phase   : {state.current_phase}",
        f"  gates_passed    : [{', '.join(state.gates_passed)}]",
        f"  flags           : {json.dumps(state.flags, sort_keys=True)}",
        f"  fast_mode       : {str(state.flags.get('fast_mode', False)).lower()}",
        f"  output_formats  : [{', '.join(state.flags.get('output_formats', []))}]",
        f"  next_gate       : {next_gate or '-'}",
        f"  next_action     : {next_hint}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Workspace resolution helper (shared with scripts/stage.py and build.py)
# ---------------------------------------------------------------------------


def resolve_workspace(workspace: Path | str | None) -> Path:
    if workspace:
        return Path(workspace).expanduser().resolve()
    env_value = os.environ.get("WORKSPACE_DIR")
    if env_value:
        return Path(env_value).expanduser().resolve()
    raise InvalidTransitionError(
        "workspace path is required (set --workspace or WORKSPACE_DIR)"
    )
