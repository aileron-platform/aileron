// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ThreadMessageItem } from "./ThreadMessageItem";
import type { UiMessage } from "./toUiMessages";

vi.mock("@/shared/hooks/useI18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const toolResult = (preview: string) => ({
  messageId: "result-1",
  isError: false,
  preview,
  byteLength: preview.length,
  lineCount: 1,
  truncated: false,
  mediaType: "text/plain",
});

describe("ThreadMessageItem", () => {
  it("renders text parts", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      parts: [{ kind: "text", text: "hello" }],
      createdAt: "t1",
    };

    const { container } = render(<ThreadMessageItem message={message} />);

    expect(screen.getByText("hello")).toBeInTheDocument();
    const agentShell = container.querySelector('[data-message-role="agent"]');
    expect(agentShell).toHaveClass("w-full");
    expect(agentShell).not.toHaveClass("border", "border-border");
  });

  it("renders user messages with the previous subtle bubble style", () => {
    const message: UiMessage = {
      id: "m1",
      role: "user",
      parts: [{ kind: "text", text: "exampleTodoWriteexample" }],
      createdAt: "t1",
    };

    const { container } = render(<ThreadMessageItem message={message} />);

    const userShell = container.querySelector('[data-message-role="user"]');
    expect(userShell).toHaveClass("w-fit", "max-w-[80%]", "bg-primary/10");
    expect(userShell).not.toHaveClass("bg-primary", "text-primary-foreground");
  });

  it("renders text parts through markdown", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      parts: [
        {
          kind: "text",
          text: "| Tool | Result |\n|---|---|\n| TaskList | Done |",
        },
      ],
      createdAt: "t1",
    };

    render(<ThreadMessageItem message={message} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("TaskList")).toBeInTheDocument();
  });

  it("renders attachment chips", () => {
    const message: UiMessage = {
      id: "m1",
      role: "user",
      parts: [
        {
          kind: "attachment",
          name: "diagram.png",
          mimeType: "image/png",
          attachmentType: "image",
        },
        {
          kind: "attachment",
          name: "brief.pdf",
          mimeType: "application/pdf",
          attachmentType: "pdf",
        },
        {
          kind: "attachment",
          name: "notes.txt",
          mimeType: "text/plain",
          attachmentType: "text-file",
        },
      ],
      createdAt: "t1",
    };

    render(<ThreadMessageItem message={message} />);

    expect(screen.getByText("diagram.png")).toBeInTheDocument();
    expect(screen.getByText("brief.pdf")).toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
  });

  it("keeps activity and nested thinking/tool details collapsed separately", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      createdAt: "t1",
      parts: [
        { kind: "thinking", text: "Need to inspect tools before answering." },
        {
          kind: "tool",
          id: "tool1",
          name: "TaskList",
          parameters: {},
          status: "completed",
          result: toolResult("No tasks found"),
          parts: [],
        },
        { kind: "text", text: "Final answer" },
      ],
    };

    render(<ThreadMessageItem message={message} />);

    expect(
      screen.getByRole("button", { name: "aiChat.activity.finished" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Final answer")).toBeInTheDocument();
    expect(
      screen.queryByText("Need to inspect tools before answering."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("No tasks found")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "aiChat.activity.finished" }),
    );

    expect(
      screen.getByRole("button", { name: "aiChat.thinking.collapsed" }),
    ).toBeInTheDocument();
    expect(screen.getByText("TaskList")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Need to inspect tools before answering."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("No tasks found")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "aiChat.thinking.collapsed" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "(aiChat.tool.preview.showAll)" }),
    );

    expect(
      screen.getByText("Need to inspect tools before answering."),
    ).toBeInTheDocument();
    expect(screen.getByText("No tasks found")).toBeInTheDocument();
  });

  it("uses a thinking header as the collapsed label and expands the content", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      createdAt: "t1",
      parts: [{ kind: "thinking", text: "**Planning**\nNeed to inspect files." }],
    };

    render(<ThreadMessageItem message={message} />);

    fireEvent.click(screen.getByRole("button", { name: "Planning" }));

    expect(screen.getByRole("button", { name: "aiChat.thinking.expanded" })).toBeInTheDocument();
    expect(screen.getByText("Need to inspect files.")).toBeInTheDocument();
  });

  it("keeps empty thinking content expandable without adding placeholder text", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      createdAt: "t1",
      parts: [{ kind: "thinking", text: "" }],
    };

    render(<ThreadMessageItem message={message} />);

    fireEvent.click(
      screen.getByRole("button", { name: "aiChat.thinking.collapsed" }),
    );

    expect(
      screen.getByRole("button", { name: "aiChat.thinking.expanded" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("aiChat.thinking.empty")).not.toBeInTheDocument();
  });

  it("renders system init as an independent collapsed button block", () => {
    const message = {
      id: "init1",
      role: "init",
      createdAt: "t1",
      parts: [
        {
          kind: "system_init",
          agentResumeId: "be36d1e9",
          model: null,
          cwd: null,
          tools: ["Task", "Read", "mcp__terry__PermissionPrompt"],
          mcpServers: [{ name: "terry", status: "connected" }],
        },
      ],
    } as unknown as UiMessage;

    render(<ThreadMessageItem message={message} />);

    expect(
      screen.getByRole("button", { name: /aiChat.init.title/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("be36d1e9")).not.toBeInTheDocument();
    expect(screen.queryByText("Task")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /aiChat.init.title/ }));

    expect(screen.getByText("aiChat.init.agentResume")).toBeInTheDocument();
    expect(screen.getByText("be36d1e9")).toBeInTheDocument();
    expect(screen.getByText("Task")).toBeInTheDocument();
    expect(screen.getByText("PermissionPrompt")).toBeInTheDocument();
    expect(screen.getAllByText("terry").length).toBeGreaterThan(0);
    expect(screen.getByTestId("system-init-tool-chip-Task")).toHaveClass(
      "rounded-full",
      "border",
      "bg-muted/40",
    );
    expect(
      screen.getByTestId("system-init-mcp-tool-chip-PermissionPrompt"),
    ).toHaveClass("rounded-full", "border", "bg-muted/40");
  });

  it("hides zero-count system init sections", () => {
    const message = {
      id: "init-empty",
      role: "init",
      createdAt: "t1",
      parts: [
        {
          kind: "system_init",
          agentResumeId: "codex-session",
          model: null,
          cwd: null,
          tools: [],
          mcpServers: [],
        },
      ],
    } as unknown as UiMessage;

    render(<ThreadMessageItem message={message} />);

    expect(
      screen.getByRole("button", { name: "aiChat.init.title" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("aiChat.init.toolCount")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "aiChat.init.title" }));

    expect(screen.getByText("codex-session")).toBeInTheDocument();
    expect(screen.queryByText("aiChat.init.tools")).not.toBeInTheDocument();
    expect(screen.queryByText("aiChat.init.mcpServices")).not.toBeInTheDocument();
  });

  it("renders extended Claude system init capability sections when present", () => {
    const message = {
      id: "init-claude",
      role: "init",
      createdAt: "t1",
      parts: [
        {
          kind: "system_init",
          agentResumeId: "claude-session",
          model: "claude-opus-4-8",
          cwd: "/workspace",
          tools: ["Read"],
          mcpServers: [],
          slashCommands: ["review", "fix"],
          outputStyle: "concise",
          agents: ["code-reviewer"],
          skills: ["frontend-design"],
          plugins: ["github"],
        },
      ],
    } as unknown as UiMessage;

    render(<ThreadMessageItem message={message} />);

    fireEvent.click(screen.getByRole("button", { name: /aiChat.init.title/ }));

    expect(screen.getByText("aiChat.init.outputStyle")).toBeInTheDocument();
    expect(screen.getByText("concise")).toBeInTheDocument();
    expect(screen.getByText("aiChat.init.slashCommands")).toBeInTheDocument();
    expect(screen.getByText("/review")).toBeInTheDocument();
    expect(screen.getByText("/fix")).toBeInTheDocument();
    expect(screen.getByText("aiChat.init.agents")).toBeInTheDocument();
    expect(screen.getByText("code-reviewer")).toBeInTheDocument();
    expect(screen.getByText("aiChat.init.skills")).toBeInTheDocument();
    expect(screen.getByText("frontend-design")).toBeInTheDocument();
    expect(screen.getByText("aiChat.init.plugins")).toBeInTheDocument();
    expect(screen.getByText("github")).toBeInTheDocument();
  });

  it("dispatches Aileron MCP tool parts through the registry", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      createdAt: "t1",
      parts: [
        {
          kind: "tool",
          id: "tool1",
          name: "mcp__aileron__ask_user_question",
          parameters: {
            id: "mock",
            title: "Mock question",
            questions: [
              {
                id: "answer",
                label: "Answer",
                type: "radio",
                options: ["Yes", "No"],
              },
            ],
          },
          status: "completed",
          result: toolResult("Question form delivered to the user."),
          parts: [],
        },
      ],
    };

    render(<ThreadMessageItem message={message} />);

    expect(screen.getByText("Mock question")).toBeInTheDocument();
  });

  it("keeps ask_user_question visible instead of collapsing it into activity", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      createdAt: "t1",
      parts: [
        {
          kind: "tool",
          id: "tool1",
          name: "mcp__aileron__ask_user_question",
          parameters: {
            id: "mock",
            title: "Mock question",
            questions: [
              {
                id: "answer",
                label: "Answer",
                type: "radio",
                options: ["Yes", "No"],
              },
            ],
          },
          status: "completed",
          result: toolResult("Question form delivered to the user."),
          parts: [],
        },
        { kind: "text", text: "Waiting for your answer." },
      ],
    };

    render(<ThreadMessageItem message={message} />);

    expect(
      screen.queryByRole("button", { name: "aiChat.activity.finished" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Mock question")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes" })).toBeInTheDocument();
    expect(screen.getByText("Waiting for your answer.")).toBeInTheDocument();
  });

  it("keeps show_canvas_artifact visible instead of collapsing it into activity", () => {
    const message: UiMessage = {
      id: "m1",
      role: "agent",
      createdAt: "t1",
      parts: [
        {
          kind: "tool",
          id: "tool1",
          name: "mcp__aileron__show_canvas_artifact",
          parameters: {
            title: "Landing page",
            route: "/landing",
          },
          status: "completed",
          result: toolResult("Canvas artifact delivered to the user."),
          parts: [],
        },
        { kind: "text", text: "Opened the canvas." },
      ],
    };

    render(
      <MemoryRouter>
        <ThreadMessageItem message={message} />
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("button", { name: "aiChat.activity.finished" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Landing page")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Landing page/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Opened the canvas.")).toBeInTheDocument();
  });
});
