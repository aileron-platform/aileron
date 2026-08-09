from __future__ import annotations

from pathlib import Path


def test_runtime_quickstart_is_discoverable(skill_root: Path) -> None:
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    quickstart = skill_root / "references" / "runtime-quickstart.md"

    assert "references/runtime-quickstart.md" in skill_text
    assert quickstart.exists()


def test_runtime_quickstart_contains_common_operational_facts(skill_root: Path) -> None:
    text = (skill_root / "references" / "runtime-quickstart.md").read_text(encoding="utf-8")

    for heading in [
        "State Commands",
        "Phase Loading",
        "Imagegen Adoption",
        "Canvas Publishing",
        "Output Placement",
    ]:
        assert f"## {heading}" in text


def test_docs_allow_mutation_output_instead_of_mandatory_duplicate_show(skill_root: Path) -> None:
    docs = [
        (skill_root / "SKILL.md").read_text(encoding="utf-8"),
        (skill_root / "phases" / "00-overview.md").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(docs).lower()

    assert "mutation output" in combined
    assert "re-run `show`" not in combined
    assert "rerun `show`" not in combined
    assert "after any successful `init`, `pass`, `enter`, `set-flag`, or `reset`" not in combined


def test_runtime_docs_describe_resume_discovery(skill_root: Path) -> None:
    docs = [
        skill_root / "SKILL.md",
        skill_root / "phases" / "00-overview.md",
        skill_root / "references" / "runtime-quickstart.md",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "stage.py resume --workspace /workspace" in text
        assert "stage.py resume <query> --workspace /workspace" in text
        assert "stage.py list --workspace /workspace" in text
        assert "stage.py list --all --workspace /workspace" in text


def test_ppt_skill_entrances_are_task_oriented(skill_root: Path) -> None:
    design_flow = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    revision_root = skill_root.parent / "ppt-revision-flow"
    revision_skill = revision_root / "SKILL.md"

    assert revision_skill.exists()
    revision_text = revision_skill.read_text(encoding="utf-8")
    assert "$ppt-revision-flow" in design_flow
    assert "new deck" in design_flow.lower()
    assert "completed deck" in revision_text.lower()
    assert "/workspace/.aileron/canvases/ppt-design-flow/<session-id>/" in revision_text
    assert "stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace" in revision_text
    assert "build.py --phase=revision" in revision_text
    assert "stage.py complete-revision --session-id <YYYY-MM-DD-title-slug> --workspace /workspace" in revision_text
    assert "does not add, delete, reorder, or re-plan slides" in revision_text


def test_runtime_quickstart_describes_revision_commands(skill_root: Path) -> None:
    text = (skill_root / "references" / "runtime-quickstart.md").read_text(encoding="utf-8")

    assert "stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace" in text
    assert "build.py --phase=revision" in text
    assert "stage.py complete-revision --session-id <YYYY-MM-DD-title-slug> --workspace /workspace" in text
    assert "$ppt-revision-flow" in text


def test_subagent_generation_runtime_contract_is_documented(skill_root: Path) -> None:
    runtime_path = skill_root / "references" / "subagent-generation-runtime.md"

    assert runtime_path.exists()

    text = runtime_path.read_text(encoding="utf-8")
    required_terms = [
        "bounded subagent workers",
        "Payload Containment Rule",
        "single-image worker",
        "fork_context:false",
        "A worker MUST call image generation or image editing at most once",
        "A worker MUST adopt exactly one output file",
        "Worker Completion Signal",
        "worker final message MUST be user-safe",
        "MUST NOT contain JSON",
        "The main thread MUST NOT parse worker final messages",
        "file-backed state",
        "Assign exactly one final slide image",
        "Assign exactly one candidate image",
        "Assign exactly one style-preview image",
        "requires three separate workers",
        "worker input",
        "Worker Completion Signal",
        "adopted_path",
        "manifest_path",
        "final-pages.json",
        "candidate mapping",
        "subagent-runs.json",
        "required worker ledger",
        "base64",
        "data URL",
        "markdown image",
        "imageGeneration",
        "image_generation_call",
        "adopt files before reporting success",
        "explicit user authorization",
        "must ask for authorization",
        "MUST NOT call image-generation or image-editing tools directly",
        "Do not use a \"direct path\" fallback",
        "停止產圖流程",
        "/workspace/.aileron/canvases/ppt-design-flow/<session-id>/",
    ]

    for term in required_terms:
        assert term in text


def test_design_generation_docs_require_subagent_workers(skill_root: Path) -> None:
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    generation_text = (skill_root / "phases" / "50-generation.md").read_text(encoding="utf-8")
    combined = f"{skill_text}\n{generation_text}"

    assert "references/subagent-generation-runtime.md" in combined
    assert "bounded single-image subagent workers" in combined
    assert "fork_context:false" in combined
    assert "call image generation/editing at most once" in combined
    assert "adopt exactly one file" in combined
    assert "one short user-safe sentence" in combined
    assert "must not return JSON" in combined
    assert "Assign exactly one final slide image" in combined
    assert "Each worker handles exactly one candidate image" in combined
    assert "subagent-runs.json" in combined
    assert "final-pages.json" in combined
    assert "candidate mapping" in combined
    assert "base64" in combined
    assert "data URLs" in combined
    assert "markdown image embeds" in combined
    assert "raw `imageGeneration`" in combined
    assert "explicit user authorization" in combined
    assert "MUST NOT call image generation" in combined or "must not call image-generation" in combined
    assert "If authorization is missing or denied, stop" in combined


def test_revision_docs_reuse_subagent_generation_runtime(skill_root: Path) -> None:
    revision_root = skill_root.parent / "ppt-revision-flow"
    docs = [
        revision_root / "SKILL.md",
        revision_root / "phases" / "30-review-retouch.md",
        revision_root / "references" / "revision-runtime.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "references/subagent-generation-runtime.md" in combined
    assert "bounded single-image subagent workers" in combined
    assert "including a single page" in combined or "including one selected page" in combined
    assert "There is no single-page direct-generation exception" in combined
    assert "fork_context:false" in combined
    assert "call image generation/editing at most once" in combined
    assert "adopt exactly one revised" in combined
    assert "one short user-safe sentence" in combined
    assert "must not contain JSON or internal paths" in combined
    assert "subagent-runs.json" in combined
    assert "immediately adopt" in combined
    assert "selected page ids" in combined
    assert "current revision request" in combined
    assert "adopted files" in combined
    assert "base64" in combined
    assert "data URLs" in combined
    assert "markdown image embeds" in combined
    assert "explicit user authorization" in combined
    assert "must ask for authorization" in combined
    assert "The main thread must never generate or edit revised page images directly" in combined


def test_revision_docs_apply_user_facing_language_guardrail(skill_root: Path) -> None:
    revision_root = skill_root.parent / "ppt-revision-flow"
    docs = [
        revision_root / "SKILL.md",
        revision_root / "phases" / "30-review-retouch.md",
        revision_root / "phases" / "40-reexport.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "User-facing language guardrail" in combined
    assert "Can the user see it, choose it, or act on it?" in combined
    assert "user-visible outcome" in combined
    assert "next action" in combined
    assert "decision the user can make" in combined
    assert "implementation details are internal" in combined
    assert "worker metadata is internal" in combined
    assert "Do not paste worker JSON" in combined


def test_review_fast_mode_disclosure_is_user_facing(skill_root: Path) -> None:
    text = (skill_root / "phases" / "60-review.md").read_text(encoding="utf-8")

    assert "Fast-mode disclosure" in text
    assert "user-facing bullet list" in text
    assert "Do not include raw `stage.py` commands" in text
    assert "重選風格" in text
    assert "重做頁規劃" in text


def test_subagent_worker_json_is_internal_only(skill_root: Path) -> None:
    runtime_text = (skill_root / "references" / "subagent-generation-runtime.md").read_text(
        encoding="utf-8"
    )
    generation_text = (skill_root / "phases" / "50-generation.md").read_text(
        encoding="utf-8"
    )
    style_text = (skill_root / "phases" / "30-style.md").read_text(encoding="utf-8")
    combined = f"{runtime_text}\n{generation_text}\n{style_text}"

    assert "Worker Completion Signal" in combined
    assert "Do not paste worker JSON" in combined
    assert "summarize completion in user-facing prose" in combined
    assert "Worker Completion Signal" in combined
    assert "worker final message MUST be user-safe" in combined
    assert "The main thread MUST NOT parse worker final messages" in combined
    assert "Final message must be one short user-safe sentence with no JSON and no internal paths" in combined
    assert "compact JSON" not in combined
    assert "Use compact JSON" not in combined
    assert "預覽頁已準備好" in combined


def test_imagegen_style_preview_uses_subagent_runtime(skill_root: Path) -> None:
    style_text = (skill_root / "phases" / "30-style.md").read_text(encoding="utf-8")
    runtime_text = (skill_root / "references" / "subagent-generation-runtime.md").read_text(
        encoding="utf-8"
    )
    combined = f"{style_text}\n{runtime_text}"

    assert "imagegen style preview" in combined
    assert "preview mode is `imagegen`" in combined
    assert "style-preview worker" in combined
    assert "one single-image style-preview worker per preview image" in combined
    assert "requires three separate workers" in combined
    assert "preview_page_role" in combined
    assert "--slot style-preview" in combined
    assert "preview_mode=svg" in combined


def test_user_facing_language_guardrail_hides_internal_runtime_terms(skill_root: Path) -> None:
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    review_text = (skill_root / "phases" / "60-review.md").read_text(encoding="utf-8")
    conversation_text = (skill_root / "references" / "conversation_framework.md").read_text(
        encoding="utf-8"
    )
    preview_flow_text = (skill_root / "references" / "preview-flow.md").read_text(
        encoding="utf-8"
    )
    combined = f"{skill_text}\n{review_text}\n{conversation_text}\n{preview_flow_text}"

    assert "User-facing language guardrail" in combined
    assert "user-visible outcome" in combined
    assert "next action" in combined
    assert "decision the user can make" in combined
    assert "implementation details are internal" in combined
    assert "tools, file paths, data structures, runtime state, or orchestration steps" in combined
    assert "複製回饋內容" in combined
    assert "paste the copied JSON" not in review_text
    assert "複製出的 JSON" not in conversation_text


def test_user_facing_guardrail_translates_internal_json_objects(skill_root: Path) -> None:
    docs = [
        skill_root / "SKILL.md",
        skill_root / "phases" / "50-generation.md",
        skill_root / "references" / "subagent-generation-runtime.md",
        skill_root.parent / "ppt-revision-flow" / "SKILL.md",
        skill_root.parent / "ppt-revision-flow" / "phases" / "30-review-retouch.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "Internal JSON translation prompt" in combined
    assert "Does this look like an internal JSON object?" in combined
    assert "translate it into a user-facing sentence" in combined
    assert "updated_pages" in combined
    assert "manifest_updated" in combined
    assert "final single-candidate" in combined
    assert "已完成 S09 和 S10 的更新" in combined


def test_design_flow_uses_question_forms_for_structured_choices(skill_root: Path) -> None:
    docs = [
        skill_root / "SKILL.md",
        skill_root / "phases" / "00-overview.md",
        skill_root / "phases" / "10-intake.md",
        skill_root / "phases" / "20-content-basis.md",
        skill_root / "phases" / "30-style.md",
        skill_root / "phases" / "40-planning.md",
        skill_root / "phases" / "50-generation.md",
        skill_root / "phases" / "60-review.md",
        skill_root / "references" / "subagent-generation-runtime.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "Structured question tool rule" in combined
    assert "mcp__aileron__ask_user_question" in combined
    assert "every user-facing question" in combined
    assert "ppt-session-selection" in combined
    assert "ppt-intake-essentials" in combined
    assert "ppt-needs-confirmation" in combined
    assert "ppt-content-basis-mode" in combined
    assert "ppt-style-boundaries" in combined
    assert "ppt-style-preview-action" in combined
    assert "ppt-style-regeneration-decision" in combined
    assert "ppt-style-refinement-base" in combined
    assert "ppt-style-breakdown-confirmation" in combined
    assert "ppt-pre-generation-confirmation" in combined
    assert "ppt-generation-branch" in combined
    assert "ppt-subagent-authorization" in combined
    assert "ppt-fast-mode-recovery" in combined
    assert "ppt-review-approval" in combined
    assert "整體色系" in combined
    assert "設計路線" in combined
    assert "風格方向數量" in combined
    assert "預覽方式" in combined
    assert "Output format selection" in combined
    assert "詳細 flow" in combined
    assert "快速 flow" in combined
    assert "SVG 快速預覽" in combined
    assert "imagegen 高擬真預覽" in combined
    assert "HTML 簡報" in combined
    assert "Do not use question tools" in combined
    assert "free-form review feedback" in combined


def test_revision_flow_uses_question_forms_for_structured_choices(skill_root: Path) -> None:
    revision_root = skill_root.parent / "ppt-revision-flow"
    docs = [
        revision_root / "SKILL.md",
        revision_root / "phases" / "30-review-retouch.md",
        revision_root / "phases" / "40-reexport.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "Structured question tool rule" in combined
    assert "mcp__aileron__ask_user_question" in combined
    assert "every user-facing question" in combined
    assert "ppt-revision-approval" in combined
    assert "Output format selection" in combined
    assert "Do not use question tools" in combined
    assert "free-form revision feedback" in combined


def test_preview_progress_guardrail_uses_user_visible_prompt(skill_root: Path) -> None:
    style_text = (skill_root / "phases" / "30-style.md").read_text(encoding="utf-8")

    assert "user-visible prompt" in style_text
    assert "what the user will see next" in style_text
    assert "what decision they can make next" in style_text
    assert "implementation details are internal" in style_text
    assert "正在整理風格候選" in style_text


def test_style_preview_requires_image_binding_check_before_publishing(skill_root: Path) -> None:
    style_text = (skill_root / "phases" / "30-style.md").read_text(encoding="utf-8")

    assert "Preview Image Binding Rule" in style_text
    assert "Do not tell the user the preview page is ready until this check passes" in style_text
    assert "every active preview image" in style_text
    assert "no placeholder preview images" in style_text
    assert "referenced image file exists" in style_text
