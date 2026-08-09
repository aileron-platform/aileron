import { useRef, useState, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown, ChevronRight } from "lucide-react";
import { MarkdownContent } from "@/shared/components/markdown/MarkdownContent";
import { useI18n } from "@/shared/hooks/useI18n";
import { cn } from "@/shared/utils/cn";
import { getFileIcon } from "@/shared/components/file-workbench";
import { SystemInitWidget } from "./SystemInitWidget";
import { resolveToolPart } from "./toolPartRegistry";
import type { UiMessage, UiMessagePart } from "./toUiMessages";

interface ThreadMessageItemProps {
  message: UiMessage;
  activityState?: "finished" | "working";
}

const roleClassName: Record<UiMessage["role"], string> = {
  user: "ml-auto rounded-md bg-primary/10 p-2 text-foreground",
  agent: "mr-auto text-foreground",
  system: "mx-auto text-muted-foreground",
  init: "mr-auto text-muted-foreground",
  error:
    "mr-auto rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-destructive",
};

const widthClassName: Record<UiMessage["role"], string> = {
  user: "w-fit max-w-[80%]",
  agent: "w-full",
  system: "w-full",
  init: "w-full",
  error: "max-w-[min(42rem,100%)]",
};

const shouldTranslate = (text: string) => text.startsWith("aiChat.");

const findLastTextPartIndex = (parts: UiMessagePart[]) => {
  for (let index = parts.length - 1; index >= 0; index -= 1) {
    if (parts[index]?.kind === "text") return index;
  }
  return -1;
};

const getThinkingTitle = (text: string): string | null => {
  const match = text.match(/^\*\*(.*?)\*\*/);
  return match ? (match[1]?.trim() ?? null) : null;
};

const isInteractiveAileronTool = (part: UiMessagePart): boolean => {
  if (part.kind !== "tool") return false;
  if (
    part.name === "mcp__aileron__ask_user_question" ||
    part.name === "mcp__aileron__show_canvas_artifact"
  ) {
    return true;
  }
  return (part.parts ?? []).some(isInteractiveAileronTool);
};

const ThinkingPart = ({ text }: { text: string }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const title = getThinkingTitle(text) ?? t("aiChat.thinking.collapsed");

  if (!expanded) {
    return (
      <button
        type="button"
        className="flex min-w-0 items-center gap-1 py-1 text-sm italic text-muted-foreground"
        onClick={() => setExpanded(true)}
      >
        <ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="truncate">{title}</span>
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-2 text-sm italic text-muted-foreground">
      <button
        type="button"
        className="flex w-fit items-center gap-1 py-1"
        onClick={() => setExpanded(false)}
      >
        <ChevronDown className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="truncate">{t("aiChat.thinking.expanded")}</span>
      </button>
      <MarkdownContent
        content={text}
        variant="compact"
        className="break-words text-muted-foreground"
      />
    </div>
  );
};

const ActivityParts = ({ parts }: { parts: ReactNode[] }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: parts.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 52,
    overscan: 6,
  });

  if (parts.length <= 50) {
    return <div className="flex max-h-[50dvh] flex-col gap-2 overflow-y-auto">{parts}</div>;
  }
  return (
    <div ref={containerRef} className="max-h-[50dvh] overflow-y-auto">
      <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((row) => (
          <div
            key={row.key}
            ref={virtualizer.measureElement}
            data-index={row.index}
            className="absolute left-0 top-0 w-full pb-2"
            style={{ transform: `translateY(${row.start}px)` }}
          >
            {parts[row.index]}
          </div>
        ))}
      </div>
    </div>
  );
};

export const ThreadMessageItem = ({
  message,
  activityState = "finished",
}: ThreadMessageItemProps) => {
  const { t } = useI18n();
  const [activityExpanded, setActivityExpanded] = useState(false);
  const lastTextPartIndex =
    message.role === "agent" ? findLastTextPartIndex(message.parts) : -1;
  const containsInteractiveAileronTool = message.parts.some(isInteractiveAileronTool);
  const hasCollapsibleActivity =
    message.role === "agent" &&
    !containsInteractiveAileronTool &&
    message.parts.length > 1 &&
    lastTextPartIndex > 0;
  const activityParts = hasCollapsibleActivity
    ? message.parts.slice(0, lastTextPartIndex)
    : [];
  const visibleParts = hasCollapsibleActivity
    ? message.parts.slice(lastTextPartIndex)
    : message.parts;

  const renderPart = (part: UiMessagePart, index: number) => {
    if (part.kind === "text") {
      const text = shouldTranslate(part.text)
        ? t(part.text, { defaultValue: part.text })
        : part.text;
      return (
        <MarkdownContent
          key={`${message.id}-text-${index}`}
          content={text}
          variant="chat"
        />
      );
    }

    if (part.kind === "thinking") {
      const text = shouldTranslate(part.text)
        ? t(part.text, { defaultValue: part.text })
        : part.text;
      return (
        <ThinkingPart key={`${message.id}-thinking-${index}`} text={text} />
      );
    }

    if (part.kind === "attachment") {
      return (
        <div
          key={`${message.id}-attachment-${index}`}
          className="flex max-w-full items-center gap-2 rounded-md border border-border/70 bg-background/60 px-2 py-1 text-xs text-foreground"
        >
          <span className="shrink-0" aria-hidden="true">
            {getFileIcon(part.name)}
          </span>
          <span className="max-w-52 truncate" title={part.name}>
            {part.name}
          </span>
        </div>
      );
    }

    if (part.kind === "system_init") {
      return (
        <SystemInitWidget
          key={`${message.id}-system-init-${index}`}
          agentResumeId={part.agentResumeId}
          model={part.model}
          cwd={part.cwd}
          tools={part.tools}
          slashCommands={part.slashCommands}
          outputStyle={part.outputStyle}
          agents={part.agents}
          skills={part.skills}
          plugins={part.plugins}
          mcpServers={part.mcpServers}
        />
      );
    }

    const ToolPart = resolveToolPart(part.name);
    const toolResult = part.result && shouldTranslate(part.result.preview)
      ? {
          ...part.result,
          preview: t(part.result.preview, { defaultValue: part.result.preview }),
        }
      : part.result;
    return (
      <ToolPart
        key={part.id}
        id={part.id}
        name={part.name}
        parameters={part.parameters}
        status={part.status}
        result={toolResult}
        parts={part.parts}
      />
    );
  };

  return (
    <div
      className={cn(
        "flex w-full",
        message.role === "user" ? "justify-end" : "justify-start",
      )}
    >
      <div
        data-message-role={message.role}
        className={cn(
          "space-y-3 text-sm",
          widthClassName[message.role],
          roleClassName[message.role],
        )}
      >
        {hasCollapsibleActivity && (
          <div className="flex flex-col gap-1">
            <button
              type="button"
              className="flex w-fit items-center gap-1 py-1 text-sm text-muted-foreground opacity-80 transition-opacity hover:opacity-100"
              onClick={() => setActivityExpanded((expanded) => !expanded)}
            >
              <span>{t(`aiChat.activity.${activityState}`)}</span>
              {activityExpanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />
              )}
            </button>
            {activityExpanded && (
              <ActivityParts parts={activityParts.map(renderPart)} />
            )}
          </div>
        )}
        {visibleParts.map((part, index) =>
          renderPart(part, activityParts.length + index),
        )}
      </div>
    </div>
  );
};
