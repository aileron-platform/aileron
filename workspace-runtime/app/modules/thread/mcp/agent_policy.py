from __future__ import annotations

from app.modules.thread.domain.tool_names import CANVAS_TOOL_NAME, QUESTION_TOOL_NAME

POLICY_INTRO = (
    "Aileron platform MCP tools are available for canvas artifacts and "
    "structured user questions. These tool-use requirements are mandatory."
)

# What deliberately does not live here:
# - Canvas workspace layout, manifest authoring, and preview mechanics belong to
#   the aileron-web-canvas skill.
# - Discovery sequencing and question selection belong to the active skill.
# One rule has one owner. Keep this policy limited to routing and completion.
CANVAS_POLICY_BODY_BYTE_BUDGET = 560

CANVAS_POLICY_BODY = (
    "For ANY task that produces a user-facing web preview (HTML page, "
    "Next.js app, dashboard, prototype, deck, or other visual web artifact), "
    "the aileron-web-canvas skill owns the workflow: load it and follow it "
    "exactly. Do not improvise its steps from memory.\n\n"
    "Completion condition: the task is not finished until "
    "/workspace/.aileron/canvas.json exists and {canvas_tool} has been called "
    "for the ready artifact. Writing files, printing a path, or pasting HTML "
    "into the chat is not delivery."
)

QUESTION_POLICY_BODY = (
    "For ANY task that needs a structured answer from the user (multiple "
    "choice, form fields, confirmations), or ANY clarifying question that "
    "expects the user to answer (missing requirements, choices, confirmations, "
    "or follow-up details), you MUST use {question_tool} instead of asking "
    "in plain text. Do not use AskUserQuestion, the bare ask_user_question "
    "name, or any non-Aileron question tool for these Aileron question forms. "
    "Hard cap: 5 questions. A question earns its place only if its answer "
    "genuinely changes what you would build for this request; count before "
    "emitting and remove the least decision-critical questions until 5 or "
    "fewer remain. Set each question's default to your best inference from "
    "the user's brief so the user confirms rather than fills. Leave default "
    "unset only when you genuinely have no basis to guess. "
    "After {question_tool} delivers the form, end the turn immediately and "
    "wait for a follow-up user message. Never infer, invent, or fabricate user "
    "answers, and never continue work from assumed answers."
)


def aileron_agent_policy_prompt(
    *,
    canvas_tool: str = CANVAS_TOOL_NAME,
    question_tool: str = QUESTION_TOOL_NAME,
) -> str:
    return "\n\n".join(
        (
            POLICY_INTRO,
            CANVAS_POLICY_BODY.format(canvas_tool=canvas_tool),
            QUESTION_POLICY_BODY.format(question_tool=question_tool),
        )
    )


AILERON_MCP_POLICY_PROMPT = aileron_agent_policy_prompt()
AILERON_OPENCODE_POLICY_PROMPT = aileron_agent_policy_prompt(
    canvas_tool="aileron_show_canvas_artifact",
    question_tool="aileron_ask_user_question",
)
