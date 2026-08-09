// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import type { ComponentType, ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { CanvasArtifactWidget } from "./CanvasArtifactWidget";
import { QuestionFormWidget } from "./QuestionFormWidget";
import { resolveToolPart } from "./toolPartRegistry";
import type { UiToolResult } from "./toUiMessages";

vi.mock("@/shared/hooks/useI18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const DefaultToolPart = resolveToolPart("__unknown_default_tool__");

const toolResult = (preview: string, truncated = false): UiToolResult => ({
  messageId: "result-1",
  isError: false,
  preview,
  byteLength: new TextEncoder().encode(preview).byteLength,
  lineCount: preview === "" ? 0 : preview.split("\n").length,
  truncated,
  mediaType: "text/plain",
});

const render = (ui: ReactElement) => rtlRender(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {ui}
  </QueryClientProvider>,
);

const hasExactText =
  (text: string) =>
  (_content: string, element: Element | null): boolean =>
    element?.textContent === text &&
    Array.from(element.children).every((child) => child.textContent !== text);

describe("toolPartRegistry", () => {
  it("resolves canonical tool names without compatibility aliases", () => {
    expect(resolveToolPart("mcp__aileron__ask_user_question")).toBe(QuestionFormWidget);
    expect(resolveToolPart("mcp__aileron__show_canvas_artifact")).toBe(CanvasArtifactWidget);
    expect(resolveToolPart("Bash")).not.toBe(DefaultToolPart);
    expect(resolveToolPart("AskUserQuestion")).toBe(DefaultToolPart);
    expect(resolveToolPart("ShowCanvasArtifact")).toBe(DefaultToolPart);
    expect(resolveToolPart("shell")).toBe(DefaultToolPart);
  });

  it("falls back to DefaultToolPart for unknown names", () => {
    expect(resolveToolPart("SomeFutureTool")).toBe(DefaultToolPart);
  });

  it("clamps long default tool labels to three visual lines", () => {
    const path = `/root/${"nested/".repeat(80)}file.txt`;

    render(
      <DefaultToolPart
        name="UnknownTool"
        parameters={{ file_path: path }}
        status="completed"
        result={toolResult("Done")}
      />,
    );

    expect(screen.getByText(`UnknownTool(${path})`)).toHaveClass("line-clamp-3");
  });

  it.each([
    ["empty", ""],
    ["whitespace-only", " \n\t "],
  ])("does not show all for a %s default result", (_label, result) => {
    render(
      <DefaultToolPart
        name="UnknownTool"
        parameters={{}}
        status="completed"
        result={toolResult(result)}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    ).not.toBeInTheDocument();
  });

  it("shows Terragon-style result preview and show less control", () => {
    render(
      <DefaultToolPart
        name="TaskList"
        parameters={{}}
        status="completed"
        result={toolResult("No tasks found")}
      />,
    );

    expect(screen.getByText("└")).toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.preview.done")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("No tasks found")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    );

    expect(screen.getByText("No tasks found")).toBeInTheDocument();
    expect(screen.getByText("No tasks found").closest("div")).toHaveClass(
      "border",
      "border-border",
      "rounded-md",
    );
    expect(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showLess)" }),
    ).toBeInTheDocument();
  });

  it("preserves line breaks when expanding default TaskList output", () => {
    render(
      <DefaultToolPart
        name="TaskList"
        parameters={{}}
        status="completed"
        result={toolResult([
          "#1 [pending] example 1: example",
          "#2 [pending] example 2: example",
          "#3 [pending] example 3: example",
        ].join("\n"))}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    );

    const taskListOutput = [
      "#1 [pending] example 1: example",
      "#2 [pending] example 2: example",
      "#3 [pending] example 3: example",
    ].join("\n");
    const expandedPre = screen.getByText(
      (_content, element) =>
        element?.tagName === "PRE" && element.textContent === taskListOutput,
    );

    expect(expandedPre).toBeInTheDocument();
    expect(expandedPre.textContent).toBe(taskListOutput);
  });

  it("renders a three-line Bash preview and expands the complete output", () => {
    const BashTool = resolveToolPart("Bash");
    const output = [
      " M file-a.ts",
      "?? file-b.ts",
      "?? file-c.ts",
      "?? file-d.ts",
    ].join("\n");

    render(
      <BashTool
        name="Bash"
        parameters={{ command: "git status --short" }}
        status="completed"
        result={toolResult(output, true)}
      />,
    );

    expect(screen.getByText("Bash")).toBeInTheDocument();
    expect(screen.getByText("(git status --short)")).toBeInTheDocument();
    expect(screen.getByText("└")).toBeInTheDocument();
    expect(screen.getByText("M file-a.ts")).toBeInTheDocument();
    expect(screen.getByText("?? file-b.ts")).toBeInTheDocument();
    expect(screen.getByText("?? file-c.ts")).toBeInTheDocument();
    expect(screen.getByText("… +1 aiChat.tool.lines.more")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.preview.showAll", { selector: "h2" })).toBeInTheDocument();
  });

  it("clamps the canonical Bash command header to three visual lines", () => {
    const BashTool = resolveToolPart("Bash");
    const command = `printf '${"x".repeat(600)}'`;

    render(
      <BashTool
        name="Bash"
        parameters={{ command }}
        status="completed"
        result={toolResult("done")}
      />,
    );

    expect(screen.getByText(`(${command})`).closest("div")).toHaveClass(
      "line-clamp-3",
    );
  });

  it("shows a clamped expandable Bash preview when one of the first three lines exceeds 500 characters", () => {
    const BashTool = resolveToolPart("Bash");
    const output = ["x".repeat(501), "second line", "third line"].join("\n");

    render(
      <BashTool
        name="Bash"
        parameters={{ command: "print output" }}
        status="completed"
        result={toolResult(output, true)}
      />,
    );

    const preview = screen.getByText(
      (_content, element) =>
        element?.tagName === "PRE" && element.textContent === output,
    );
    expect(preview).toHaveClass("line-clamp-3", "whitespace-pre-wrap");
    expect(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not expand Bash output with at most three lines of 500 characters or fewer", () => {
    const BashTool = resolveToolPart("Bash");

    render(
      <BashTool
        name="Bash"
        parameters={{ command: "print output" }}
        status="completed"
        result={toolResult(["x".repeat(500), "second line", "third line"].join("\n"))}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["empty", ""],
    ["whitespace-only", " \n\t "],
  ])("does not show all for %s Bash output", (_label, result) => {
    const BashTool = resolveToolPart("Bash");

    render(
      <BashTool
        name="Bash"
        parameters={{ command: "true" }}
        status="completed"
        result={toolResult(result)}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.lines.noOutput")).toBeInTheDocument();
  });

  it("renders Edit as Update with a collapsed diff summary", () => {
    const EditTool = resolveToolPart("Edit");

    render(
      <EditTool
        name="Edit"
        parameters={{
          file_path: "/root/repo/demo_tools.md",
          old_string: "## Skills example\nexample...",
          new_string: "## Skills example\n✅ Skills example，example：\n- `/run`",
        }}
        status="completed"
        result={toolResult("The file /root/repo/demo_tools.md has been updated successfully.")}
      />,
    );

    expect(screen.getByText("aiChat.tool.edit.update")).toBeInTheDocument();
    expect(screen.getByText("(/root/repo/demo_tools.md)")).toBeInTheDocument();
    expect(screen.getByText("+3")).toBeInTheDocument();
    expect(screen.getByText("-2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "(aiChat.tool.edit.showDiff)" })).toBeInTheDocument();
    expect(screen.queryByText("example...")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "(aiChat.tool.edit.showDiff)" }));

    expect(screen.getByText("-example...")).toBeInTheDocument();
    expect(screen.getByText("+✅ Skills example，example：")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "(aiChat.tool.edit.hideDiff)" })).toBeInTheDocument();
  });

  it("renders Task with nested tool parts behind a Terragon-style tools toggle", () => {
    const TaskTool = resolveToolPart("Task") as ComponentType<{
      name: string;
      parameters: Record<string, unknown>;
      status: "pending" | "completed" | "error";
      result?: UiToolResult;
      parts: Array<{
        kind: "tool";
        id: string;
        name: string;
        parameters: Record<string, unknown>;
        status: "completed";
        result: UiToolResult;
        parts: [];
      }>;
    }>;

    render(
      <TaskTool
        name="Task"
        parameters={{ description: "Inspect source files" }}
        status="completed"
        result={toolResult("Inspected source files")}
        parts={[
          {
            kind: "tool",
            id: "read-1",
            name: "Read",
            parameters: { file_path: "toolPartRegistry.tsx" },
            status: "completed",
            result: toolResult("export const TOOL_PART_REGISTRY = {}"),
            parts: [],
          },
        ]}
      />,
    );

    expect(screen.getByText("Task")).toBeInTheDocument();
    expect(screen.getByText("(Inspect source files)")).toBeInTheDocument();
    expect(screen.getByText("1 aiChat.tool.task.tools")).toBeInTheDocument();
    expect(screen.queryByText("Read")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "(aiChat.tool.task.showAllTools)" }),
    );

    expect(screen.getByText("aiChat.tool.task.showingAllTools")).toBeInTheDocument();
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("(toolPartRegistry.tsx)")).toBeInTheDocument();
  });

  it("renders Skill through the Terragon-style default tool fallback", () => {
    const SkillTool = resolveToolPart("Skill");

    expect(SkillTool).toBe(DefaultToolPart);

    render(
      <SkillTool
        name="Skill"
        parameters={{ skill: "run" }}
        status="completed"
        result={toolResult("Launching skill: run")}
      />,
    );

    expect(screen.getByText("Skill(run)")).toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.preview.done")).toBeInTheDocument();
    expect(screen.queryByText("Launching skill: run")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    );

    expect(screen.getByText("Launching skill: run")).toBeInTheDocument();
    expect(screen.queryByText("skill")).not.toBeInTheDocument();
    expect(screen.getByText("Launching skill: run").closest("div")).toHaveClass(
      "border",
      "border-border",
      "rounded-md",
    );
  });

  it("renders Write with Terragon-style line summary and expandable diff", () => {
    const WriteTool = resolveToolPart("Write");

    render(
      <WriteTool
        name="Write"
        parameters={{
          file_path: "/root/repo/demo.md",
          content: "# Demo\ncontent",
        }}
        status="completed"
        result={toolResult("File written")}
      />,
    );

    expect(screen.getByText("Write")).toBeInTheDocument();
    expect(screen.getByText("(/root/repo/demo.md)")).toBeInTheDocument();
    expect(
      screen.getByText(
        hasExactText(
          "aiChat.tool.write.wrote 2 aiChat.tool.write.lines (aiChat.tool.write.showLines)",
        ),
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "(aiChat.tool.write.showLines)" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "(aiChat.tool.write.showLines)" }));

    expect(screen.getByText("+# Demo")).toBeInTheDocument();
    expect(screen.getByText("+content")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "(aiChat.tool.write.hideLines)" })).toBeInTheDocument();
  });

  it("renders MultiEdit with Terragon-style edit summary and expandable diff", () => {
    const MultiEditTool = resolveToolPart("MultiEdit");

    render(
      <MultiEditTool
        name="MultiEdit"
        parameters={{
          file_path: "/root/repo/demo.md",
          edits: [
            { old_string: "before", new_string: "after" },
            { old_string: "old", new_string: "new" },
          ],
        }}
        status="completed"
        result={toolResult("Applied edits")}
      />,
    );

    expect(screen.getByText("MultiEdit")).toBeInTheDocument();
    expect(screen.getByText(/file_path: "\/root\/repo\/demo.md"/)).toBeInTheDocument();
    expect(screen.getByText(/edits: 2/)).toBeInTheDocument();
    expect(
      screen.getByText(
        hasExactText(
          "aiChat.tool.multiEdit.applied 2 aiChat.tool.multiEdit.edits (aiChat.tool.multiEdit.showEdits)",
        ),
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "(aiChat.tool.multiEdit.showEdits)" }));

    expect(screen.getByText("-before")).toBeInTheDocument();
    expect(screen.getByText("+after")).toBeInTheDocument();
    expect(screen.getByText("-old")).toBeInTheDocument();
    expect(screen.getByText("+new")).toBeInTheDocument();
  });

  it("renders search, list, web, and notebook tools with Terragon labels", () => {
    const GrepTool = resolveToolPart("Grep");
    const GlobTool = resolveToolPart("Glob");
    const LSTool = resolveToolPart("LS");
    const WebFetchTool = resolveToolPart("WebFetch");
    const NotebookReadTool = resolveToolPart("NotebookRead");

    const { rerender } = render(
      <GrepTool
        name="Grep"
        parameters={{ pattern: "TODO", path: "src" }}
        status="completed"
        result={toolResult("Found 2 files\nsrc/a.ts\nsrc/b.ts")}
      />,
    );
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.getByText(/pattern: "TODO"/)).toBeInTheDocument();
    expect(
      screen.getByText(
        hasExactText(
          "aiChat.tool.search.found 2 aiChat.tool.search.files (aiChat.tool.search.showFileList)",
        ),
      ),
    ).toBeInTheDocument();

    rerender(
      <GlobTool
        name="Glob"
        parameters={{ pattern: "**/*.ts" }}
        status="completed"
        result={toolResult("src/a.ts\nsrc/b.ts\nsrc/c.ts")}
      />,
    );
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();

    rerender(
      <LSTool
        name="LS"
        parameters={{ path: "/root/repo" }}
        status="completed"
        result={toolResult("- README.md\n- src\nnotes.txt")}
      />,
    );
    expect(screen.getByText("List")).toBeInTheDocument();
    expect(
      screen.getByText(
        hasExactText("aiChat.tool.ls.listed 2 aiChat.tool.ls.paths"),
      ),
    ).toBeInTheDocument();

    rerender(
      <WebFetchTool
        name="WebFetch"
        parameters={{ url: "https://example.com" }}
        status="completed"
        result={toolResult("Fetched page content")}
      />,
    );
    expect(screen.getByText("Fetch")).toBeInTheDocument();
    expect(screen.getByText("(https://example.com)")).toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.preview.done")).toBeInTheDocument();

    rerender(
      <NotebookReadTool
        name="NotebookRead"
        parameters={{ notebook_path: "/root/notebook.ipynb" }}
        status="completed"
        result={toolResult("Notebook content")}
      />,
    );
    expect(screen.getByText("NotebookRead")).toBeInTheDocument();
    expect(screen.getByText("(/root/notebook.ipynb)")).toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.preview.done")).toBeInTheDocument();
  });

  it("renders TodoWrite and TodoRead like Terragon todo tools", () => {
    const TodoWriteTool = resolveToolPart("TodoWrite");
    const TodoReadTool = resolveToolPart("TodoRead");

    const { rerender, container } = render(
      <TodoWriteTool
        name="TodoWrite"
        parameters={{
          todos: [
            { content: "Write tests", status: "completed" },
            { content: "Implement renderer", status: "in_progress" },
            { content: "Run verification", status: "pending" },
          ],
        }}
        status="completed"
        result={toolResult("Updated")}
      />,
    );

    expect(screen.getByText("Update Todos")).toBeInTheDocument();
    expect(screen.getByText("☒")).toBeInTheDocument();
    expect(screen.getByText("◼")).toBeInTheDocument();
    expect(screen.getByText("□")).toBeInTheDocument();
    expect(screen.getByText("Write tests")).toHaveClass("line-through");
    expect(screen.getByText("Implement renderer")).toHaveClass("font-semibold");

    rerender(
      <TodoReadTool
        name="TodoRead"
        parameters={{}}
        status="completed"
        result={toolResult("[]")}
      />,
    );
    expect(container).toBeEmptyDOMElement();

    rerender(
      <TodoReadTool
        name="TodoRead"
        parameters={{}}
        status="error"
        result={toolResult("Failed")}
      />,
    );
    expect(screen.getByText("Read Todos")).toBeInTheDocument();
    expect(screen.getByText("□ aiChat.tool.todo.readFailed")).toBeInTheDocument();
  });

  it("falls back to the Terragon default renderer for Edit without diff parameters", () => {
    const EditTool = resolveToolPart("Edit");

    render(
      <EditTool
        name="Edit"
        parameters={{ file_path: "/root/repo/demo.md" }}
        status="completed"
        result={toolResult("Edited file without diff payload")}
      />,
    );

    expect(screen.getByText("Edit(/root/repo/demo.md)")).toBeInTheDocument();
    expect(screen.getByText("aiChat.tool.preview.done")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "(aiChat.tool.edit.showDiff)" }),
    ).not.toBeInTheDocument();
  });

  it("renders ExitPlanMode as a Terragon-style Plan block", () => {
    const ExitPlanModeTool = resolveToolPart("ExitPlanMode");

    render(
      <ExitPlanModeTool
        name="ExitPlanMode"
        parameters={{ plan: "## Plan\n\n1. Add tests\n2. Implement renderer" }}
        status="completed"
        result={toolResult("Plan ready")}
      />,
    );

    expect(screen.getAllByText("Plan")).toHaveLength(2);
    expect(screen.getByText("Add tests")).toBeInTheDocument();
    expect(screen.getByText("Implement renderer")).toBeInTheDocument();
    expect(screen.getAllByText("Plan")[0]?.closest("div")).toHaveClass(
      "break-words",
    );
  });

  it("renders SuggestFollowupTask variants as Terragon-style suggestion cards", () => {
    const SuggestFollowupTaskTool = resolveToolPart("SuggestFollowupTask");
    const TerrySuggestFollowupTaskTool = resolveToolPart(
      "mcp__terry__SuggestFollowupTask",
    );

    const { rerender } = render(
      <SuggestFollowupTaskTool
        name="SuggestFollowupTask"
        parameters={{
          title: "Add regression coverage",
          description: "Create follow-up tests for tool renderers.",
        }}
        status="completed"
        result={toolResult("Suggested")}
      />,
    );

    expect(screen.getByText("Add regression coverage")).toBeInTheDocument();
    expect(
      screen.getByText("Create follow-up tests for tool renderers."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "aiChat.tool.followUp.start" }),
    ).toBeInTheDocument();

    rerender(
      <TerrySuggestFollowupTaskTool
        name="mcp__terry__SuggestFollowupTask"
        parameters={{
          title: "Review nested tools",
          description: "Check nested Task.parts rendering.",
        }}
        status="completed"
        result={toolResult("Suggested")}
      />,
    );

    expect(screen.getByText("Review nested tools")).toBeInTheDocument();
    expect(screen.getByText("Check nested Task.parts rendering.")).toBeInTheDocument();
  });
});
