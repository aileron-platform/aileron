#!/usr/bin/env python3
"""Agent-facing CLI for the ppt-design-flow phase state machine.

Subcommands: ``init``, ``show``, ``pass``, ``enter``, ``set-flag``, ``reset``.

The workspace path is resolved from ``--workspace`` first, then the
``WORKSPACE_DIR`` environment variable. The CLI refuses to operate when neither
source provides a path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow ``python3 scripts/stage.py`` to import the assets module without
# requiring a package install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))

import stage_state  # noqa: E402
from stage_state import (  # noqa: E402
    InvalidTransitionError,
    StageError,
    complete_revision,
    discover_sessions,
    enter_phase,
    init as state_init,
    load as state_load,
    pass_gate,
    render_resume,
    render_show,
    render_session_list,
    resolve_resume_session,
    reset,
    resolve_workspace,
    set_flag,
    revise,
)


def _shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (falls back to WORKSPACE_DIR env var).",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Canvas session id; must match ^[a-zA-Z0-9_-]{1,64}$.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stage.py",
        description="State CLI for the ppt-design-flow phase machine.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create a fresh state.json at the intake phase.")
    _shared_args(init_p)

    show_p = sub.add_parser("show", help="Print the current phase, gates, and flags.")
    _shared_args(show_p)

    pass_p = sub.add_parser("pass", help="Mark a user-confirmation gate as passed.")
    pass_p.add_argument("gate", help="Gate id (e.g. needs_confirmed, style_locked).")
    _shared_args(pass_p)

    enter_p = sub.add_parser("enter", help="Advance current_phase to the next phase.")
    enter_p.add_argument("phase", help="Phase id (e.g. content-basis, style, planning).")
    _shared_args(enter_p)

    flag_p = sub.add_parser("set-flag", help="Set a whitelisted flag value.")
    flag_p.add_argument(
        "key",
        help="Flag name (preview_mode / candidate_mode / content_basis_ready / pages_ready / fast_mode / output_formats).",
    )
    flag_p.add_argument("value", help="Flag value (boolean literal or enum string).")
    _shared_args(flag_p)

    reset_p = sub.add_parser("reset", help="Roll back to an earlier phase, truncating downstream gates and flags.")
    reset_p.add_argument("--from", dest="from_phase", required=True, help="Target phase to roll back to.")
    _shared_args(reset_p)

    revise_p = sub.add_parser("revise", help="Enter post-completion revision mode for an approved deck.")
    revise_p.add_argument(
        "--pages",
        default=None,
        help='Optional JSON list of slide ids to revise, e.g. \'["S03", "S07"]\'.',
    )
    revise_p.add_argument("--reason", default=None, help="Optional revision reason stored in request.json.")
    _shared_args(revise_p)

    complete_revision_p = sub.add_parser("complete-revision", help="Complete an active revision round.")
    _shared_args(complete_revision_p)

    list_p = sub.add_parser("list", help="List persisted ppt-design-flow sessions.")
    list_p.add_argument("--all", action="store_true", help="Include completed sessions.")
    list_p.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (falls back to WORKSPACE_DIR env var).",
    )

    resume_p = sub.add_parser("resume", help="Resume the latest or matching ppt-design-flow session.")
    resume_p.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Optional exact session id or partial slug to resume.",
    )
    resume_p.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (falls back to WORKSPACE_DIR env var).",
    )

    return parser


def _run(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    if args.command == "init":
        state = state_init(workspace, args.session_id)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "show":
        state = state_load(workspace, args.session_id)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "pass":
        state = state_load(workspace, args.session_id)
        state = pass_gate(state, args.gate)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "enter":
        state = state_load(workspace, args.session_id)
        state = enter_phase(state, args.phase)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "set-flag":
        state = state_load(workspace, args.session_id)
        state = set_flag(state, args.key, args.value)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "reset":
        state = state_load(workspace, args.session_id)
        state = reset(state, args.from_phase)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "revise":
        state = state_load(workspace, args.session_id)
        pages = None
        if args.pages:
            import json

            pages = json.loads(args.pages)
        state = revise(state, pages=pages, reason=args.reason)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "complete-revision":
        state = state_load(workspace, args.session_id)
        state = complete_revision(state)
        sys.stdout.write(render_show(state) + "\n")
        return 0
    if args.command == "list":
        discovery = discover_sessions(workspace, include_completed=args.all)
        sys.stdout.write(render_session_list(discovery) + "\n")
        return 0
    if args.command == "resume":
        summary = resolve_resume_session(workspace, args.query)
        sys.stdout.write(render_resume(summary) + "\n")
        return 0
    # argparse with required=True should make this unreachable.
    raise InvalidTransitionError(f"unknown command '{args.command}'")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except StageError as exc:
        sys.stderr.write(exc.render() + "\n")
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
