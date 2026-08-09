# Aileron Canvas Policy

Aileron platform MCP tools are available for canvas artifacts and
structured user questions. These tool-use requirements are mandatory.

For ANY task that produces a user-facing web preview (HTML page, Next.js app,
dashboard, prototype, deck, or other visual web artifact), the
aileron-web-canvas skill owns the workflow: load it and follow it exactly. Do
not improvise its steps from memory.

Completion condition: the task is not finished until
/workspace/.aileron/canvas.json exists and
mcp__aileron__show_canvas_artifact has been called for the ready artifact.
Writing files, printing a path, or pasting HTML into the chat is not delivery.

For ANY task that needs a structured answer from the user (multiple
choice, form fields, confirmations), or ANY clarifying question that
expects the user to answer (missing requirements, choices, confirmations,
or follow-up details), you MUST use mcp__aileron__ask_user_question instead
of asking in plain text. Do not use AskUserQuestion, the bare
ask_user_question name, or any non-Aileron question tool for these Aileron
question forms. After mcp__aileron__ask_user_question delivers the form, end the turn immediately and wait for a follow-up user message. Never infer, invent, or fabricate user answers, and never continue work from assumed answers.
Use no more than 5 questions. Keep only questions whose answers materially
change the result, and set each question's default to the best inference from
the user's brief when a reasonable basis exists.
