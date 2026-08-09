import type { FC, ReactNode } from "react";
import { Fragment, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Rocket, Sparkles } from "lucide-react";
import { MarkdownContent } from "@/shared/components/markdown/MarkdownContent";
import { useI18n } from "@/shared/hooks/useI18n";
import { cn } from "@/shared/utils/cn";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogHeader } from "@/shared/components/ui/dialog";
import { DialogHeading } from "@/shared/components/ui/dialog-heading";
import { CanvasArtifactWidget } from "./CanvasArtifactWidget";
import { QuestionFormWidget } from "./QuestionFormWidget";
import { useToolResultContent } from "../../hooks/useThreadTimeline";
import { aiChatToolResultQueryKey } from '../../api/threadQueryKeys';
import type { UiMessagePart, UiToolResult } from "./toUiMessages";
import type { ToolPartProps } from "./toolPartTypes";
import { useToolResultContext } from "./ToolResultContext";

const formatResult = (
  result: UiToolResult | undefined,
): string | null => {
  if (result === undefined) return null;
  return result.preview;
};

const STATUS_CLASS_NAME: Record<ToolPartProps["status"], string> = {
  pending: "bg-muted-foreground animate-pulse",
  completed: "bg-emerald-500",
  error: "bg-destructive",
  awaiting_input: "bg-amber-500 animate-pulse",
  interrupted: "bg-muted-foreground",
  canceled: "bg-muted-foreground",
  aborted_by_execution_error: "bg-destructive",
  result_missing: "bg-destructive",
};

const STATUS_TEXT_CLASS_NAME: Record<ToolPartProps["status"], string> = {
  pending: "text-muted-foreground",
  completed: "text-foreground",
  error: "text-destructive",
  awaiting_input: "text-amber-600",
  interrupted: "text-muted-foreground",
  canceled: "text-muted-foreground",
  aborted_by_execution_error: "text-destructive",
  result_missing: "text-destructive",
};

const primaryParameter = (
  parameters: Record<string, unknown>,
): string | null => {
  const value =
    parameters.command ??
    parameters.file_path ??
    parameters.path ??
    parameters.description ??
    parameters.skill;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
};

const formatToolParameters = (
  parameters: Record<string, unknown>,
  options: {
    includeKeys?: string[];
    excludeKeys?: string[];
    keyOrder?: string[];
  } = {},
) => {
  const entries = Object.entries(parameters).filter(([key]) => {
    if (options.includeKeys) return options.includeKeys.includes(key);
    if (options.excludeKeys) return !options.excludeKeys.includes(key);
    return true;
  });

  if (entries.length === 0) return null;
  if (entries.length === 1) {
    const value = entries[0]?.[1];
    if (typeof value === "string") return value;
    return JSON.stringify(value);
  }

  return entries
    .sort((a, b) => {
      const aIndex = options.keyOrder?.indexOf(a[0]) ?? -1;
      const bIndex = options.keyOrder?.indexOf(b[0]) ?? -1;
      if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
      if (aIndex !== -1) return -1;
      if (bIndex !== -1) return 1;
      return 0;
    })
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
    .join(", ");
};

const stringParameter = (
  parameters: Record<string, unknown>,
  key: string,
): string => {
  const value = parameters[key];
  return typeof value === "string" ? value : "";
};

const lineCount = (value: string): number =>
  value.length === 0 ? 0 : value.split("\n").length;

const stringLines = (value: UiToolResult | undefined) =>
  (formatResult(value) ?? "").split("\n");

const BASH_PREVIEW_LINE_LIMIT = 3;
const BASH_LONG_LINE_LENGTH = 500;

const isLongBashLine = (line: string): boolean =>
  line.length > BASH_LONG_LINE_LENGTH;

const ToolChrome: FC<{
  status: ToolPartProps["status"];
  title: string;
  argument: string | null;
  children: ReactNode;
}> = ({ status, title, argument, children }) => (
  <div className="text-sm" data-status={status}>
    <div className="flex min-w-0 items-start gap-2">
      <span className="flex h-5 items-center">
        <span
          className={cn(
            "inline-block h-2 w-2 shrink-0 rounded-full",
            STATUS_CLASS_NAME[status],
          )}
          aria-hidden="true"
        />
      </span>
      <div className="min-w-0 flex-1 font-mono">
        <div className="line-clamp-3 min-w-0 break-words font-semibold text-foreground">
          <span className="rounded-sm px-1">{title}</span>
          {argument && <span>({argument})</span>}
        </div>
        {children}
      </div>
    </div>
  </div>
);

const ToolContent: FC<{
  status: ToolPartProps["status"];
  testId?: string;
  children: ReactNode;
}> = ({ status, testId, children }) => (
  <div
    data-testid={testId}
    className={cn(
      "mt-1 grid min-w-0 grid-cols-[auto_1fr] gap-x-1.5 overflow-hidden font-mono text-sm",
      STATUS_TEXT_CLASS_NAME[status],
    )}
  >
    {children}
  </div>
);

const ToolRow: FC<{
  index: number;
  className?: string;
  testId?: string;
  children: ReactNode;
}> = ({ index, className, testId, children }) => (
  <>
    <span className="shrink-0">{index === 0 ? "└" : " "}</span>
    <div
      data-testid={testId}
      className={cn("min-w-0 overflow-hidden", className)}
    >
      {children}
    </div>
  </>
);

const ExpandButton = ({
  expanded,
  showKey,
  hideKey,
  onClick,
}: {
  expanded: boolean;
  showKey: string;
  hideKey: string;
  onClick: () => void;
}) => {
  const { t } = useI18n();
  return (
    <button
      type="button"
      className="inline text-muted-foreground/70"
      onClick={onClick}
    >
      ({t(expanded ? hideKey : showKey)})
    </button>
  );
};

const BashToolPart: FC<ToolPartProps> = ({ parameters, status, result }) => {
  const { t } = useI18n();
  const [viewerOpen, setViewerOpen] = useState(false);
  const context = useToolResultContext();
  const queryClient = useQueryClient();
  const fullContentQuery = useToolResultContent(
    context?.workspaceId ?? '',
    context?.threadId ?? '',
    result?.messageId ?? '',
    viewerOpen && Boolean(context && result?.truncated),
    context?.runtimeBaseUrl,
  );
  const command = stringParameter(parameters, "command");
  const resultText = formatResult(result) ?? "";
  const lines = resultText.trim() === "" ? [] : resultText.split("\n");
  const previewLines = lines.slice(0, BASH_PREVIEW_LINE_LIMIT);
  const hasLongPreviewLine = previewLines.some(isLongBashLine);
  const isExpandable = Boolean(result?.truncated);
  const remainingLineCount = Math.max(
    0,
    (result?.lineCount ?? lines.length) - previewLines.length,
  );

  const closeViewer = () => {
    setViewerOpen(false);
    if (context && result) {
      queryClient.removeQueries({
        queryKey: aiChatToolResultQueryKey(
          context.workspaceId,
          context.threadId,
          result.messageId,
        ),
      });
    }
  };

  return (
    <ToolChrome
      status={status}
      title="Bash"
      argument={command}
    >
      {status === "pending" ? (
        <ToolContent status={status} testId="bash-tool-output">
          <ToolRow index={0}>
            <span className="animate-pulse">
              {t("aiChat.tool.bash.running")}
            </span>
          </ToolRow>
        </ToolContent>
      ) : lines.length === 0 ? (
        <ToolContent status={status} testId="bash-tool-output">
          <ToolRow index={0}>
            <span className="text-muted-foreground">
              {t("aiChat.tool.lines.noOutput")}
            </span>
          </ToolRow>
        </ToolContent>
      ) : hasLongPreviewLine ? (
        <ToolContent status={status} testId="bash-tool-output">
          <ToolRow index={0}>
            <pre className="line-clamp-3 whitespace-pre-wrap">
              {previewLines.join("\n")}
            </pre>
            {isExpandable && (
              <ExpandButton
                expanded={false}
                showKey="aiChat.tool.preview.showAll"
                hideKey="aiChat.tool.preview.showLess"
                onClick={() => setViewerOpen(true)}
              />
            )}
          </ToolRow>
        </ToolContent>
      ) : (
        <ToolContent status={status} testId="bash-tool-output">
          {previewLines.map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="block truncate">{line}</span>
            </ToolRow>
          ))}
          {isExpandable && (
            <ToolRow index={-1}>
              <span>
                {remainingLineCount > 0 && (
                  <>… +{remainingLineCount} {t("aiChat.tool.lines.more")} </>
                )}
                <ExpandButton
                  expanded={false}
                  showKey="aiChat.tool.preview.showAll"
                  hideKey="aiChat.tool.preview.showLess"
                  onClick={() => setViewerOpen(true)}
                />
              </span>
            </ToolRow>
          )}
        </ToolContent>
      )}
      <Dialog open={viewerOpen} onOpenChange={(open) => open ? setViewerOpen(true) : closeViewer()}>
        <DialogContent
          aria-describedby={undefined}
          className="h-dvh max-h-dvh w-screen max-w-none rounded-none sm:h-[80vh] sm:max-h-[80vh] sm:w-[min(64rem,90vw)] sm:max-w-[64rem] sm:rounded-lg"
        >
          <DialogHeader>
            <DialogHeading icon={Sparkles}>{t("aiChat.tool.preview.showAll")}</DialogHeading>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-auto rounded-md border bg-zinc-950 p-3 text-zinc-50">
            {fullContentQuery.isLoading ? (
              <p>{t("aiChat.tool.resultLoading")}</p>
            ) : fullContentQuery.isError ? (
              <div className="space-y-3">
                <p>{t("aiChat.tool.resultLoadFailed")}</p>
                <Button type="button" variant="outline" onClick={() => void fullContentQuery.refetch()}>
                  {t("aiChat.tool.retryResult")}
                </Button>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5">
                {fullContentQuery.data === '' ? t("aiChat.tool.noOutput") : fullContentQuery.data}
              </pre>
            )}
          </div>
          {fullContentQuery.data !== undefined && (
            <Button type="button" variant="outline" onClick={() => void navigator.clipboard.writeText(fullContentQuery.data)}>
              {t("aiChat.tool.copyAll")}
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </ToolChrome>
  );
};

const ReadToolPart: FC<ToolPartProps> = ({ parameters, status, result }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const filePath =
    stringParameter(parameters, "file_path") || stringParameter(parameters, "path");
  const resultText = formatResult(result) ?? "";
  const lines = resultText.trim() === "" ? [] : resultText.split("\n");

  return (
    <ToolChrome
      status={status}
      title="Read"
      argument={filePath}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">
              {t("aiChat.tool.read.reading")}
            </span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {(resultText ? resultText.split("\n") : [t("aiChat.tool.preview.failed")]).map(
            (line, index) => (
              <ToolRow key={`${index}-${line}`} index={index}>
                <span className="whitespace-pre-wrap">{line}</span>
              </ToolRow>
            ),
          )}
        </ToolContent>
      ) : (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span>
              {t("aiChat.tool.read.read")}{" "}
              <span className="font-semibold">{lines.length}</span>{" "}
              {t("aiChat.tool.read.lines")}{" "}
              <ExpandButton
                expanded={expanded}
                showKey="aiChat.tool.read.showLines"
                hideKey="aiChat.tool.read.hideLines"
                onClick={() => setExpanded((value) => !value)}
              />
            </span>
          </ToolRow>
          {expanded && (
            <ToolRow
              index={1}
              className="mr-2 max-h-[350px] overflow-auto rounded-md border border-border p-1"
            >
              <pre>{resultText}</pre>
            </ToolRow>
          )}
        </ToolContent>
      )}
    </ToolChrome>
  );
};

const EditDiffLines = ({ oldString, newString }: { oldString: string; newString: string }) => (
  <pre className="max-h-[350px] overflow-auto rounded-md border border-border p-2 text-xs">
    {oldString.split("\n").map((line, index) => (
      <div key={`old-${index}`} className="text-destructive">
        -{line}
      </div>
    ))}
    {newString.split("\n").map((line, index) => (
      <div key={`new-${index}`} className="text-emerald-600">
        +{line}
      </div>
    ))}
  </pre>
);

const EditToolPart: FC<ToolPartProps> = ({ id, parameters, status, result }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const filePath = stringParameter(parameters, "file_path");
  const oldString = stringParameter(parameters, "old_string");
  const newString = stringParameter(parameters, "new_string");
  const resultText = formatResult(result) ?? "";

  if (!("old_string" in parameters) || !("new_string" in parameters)) {
    return (
      <DefaultToolPart
        id={id}
        name="Edit"
        parameters={parameters}
        status={status}
        result={result}
      />
    );
  }

  return (
    <ToolChrome
      status={status}
      title={t("aiChat.tool.edit.update")}
      argument={filePath}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t("aiChat.tool.edit.editing")}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {(resultText ? resultText.split("\n") : [t("aiChat.tool.preview.failed")]).map(
            (line, index) => (
              <ToolRow key={`${index}-${line}`} index={index}>
                <span className="whitespace-pre-wrap">{line}</span>
              </ToolRow>
            ),
          )}
        </ToolContent>
      ) : (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span>
              <span className="font-semibold text-emerald-600">
                +{lineCount(newString)}
              </span>{" "}
              <span className="font-semibold text-destructive">
                -{lineCount(oldString)}
              </span>{" "}
              <ExpandButton
                expanded={expanded}
                showKey="aiChat.tool.edit.showDiff"
                hideKey="aiChat.tool.edit.hideDiff"
                onClick={() => setExpanded((value) => !value)}
              />
            </span>
          </ToolRow>
          {expanded && (
            <ToolRow index={1}>
              <EditDiffLines oldString={oldString} newString={newString} />
            </ToolRow>
          )}
        </ToolContent>
      )}
    </ToolChrome>
  );
};

const WriteDiffLines = ({ content }: { content: string }) => (
  <pre className="max-h-[350px] overflow-auto rounded-md border border-border p-2 text-xs">
    {content.split("\n").map((line, index) => (
      <div key={`write-${index}`} className="text-emerald-600">
        +{line}
      </div>
    ))}
  </pre>
);

const WriteToolPart: FC<ToolPartProps> = ({ parameters, status, result }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const content = stringParameter(parameters, "content");
  const resultText = formatResult(result) ?? "";

  return (
    <ToolChrome
      status={status}
      title="Write"
      argument={formatToolParameters(parameters, {
        keyOrder: ["file_path"],
        excludeKeys: ["content"],
      })}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t("aiChat.tool.write.writing")}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {stringLines(result).map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="whitespace-pre-wrap">{line}</span>
            </ToolRow>
          ))}
        </ToolContent>
      ) : (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span>
              {t("aiChat.tool.write.wrote")}{" "}
              <span className="font-semibold">{lineCount(content)}</span>{" "}
              {t("aiChat.tool.write.lines")}{" "}
              <ExpandButton
                expanded={expanded}
                showKey="aiChat.tool.write.showLines"
                hideKey="aiChat.tool.write.hideLines"
                onClick={() => setExpanded((value) => !value)}
              />
            </span>
          </ToolRow>
          {expanded && (
            <ToolRow index={1} className="pr-2">
              <WriteDiffLines content={content || resultText} />
            </ToolRow>
          )}
        </ToolContent>
      )}
    </ToolChrome>
  );
};

type MultiEditEntry = {
  old_string?: unknown;
  new_string?: unknown;
};

const editsParameter = (parameters: Record<string, unknown>): MultiEditEntry[] =>
  Array.isArray(parameters.edits) ? (parameters.edits as MultiEditEntry[]) : [];

const MultiEditDiffLines = ({ edits }: { edits: MultiEditEntry[] }) => (
  <pre className="max-h-[350px] overflow-auto rounded-md border border-border p-2 text-xs">
    {edits.flatMap((edit, editIndex) => {
      const oldString =
        typeof edit.old_string === "string" ? edit.old_string : "";
      const newString =
        typeof edit.new_string === "string" ? edit.new_string : "";
      return [
        ...oldString.split("\n").map((line, index) => (
          <div key={`edit-${editIndex}-old-${index}`} className="text-destructive">
            -{line}
          </div>
        )),
        ...newString.split("\n").map((line, index) => (
          <div key={`edit-${editIndex}-new-${index}`} className="text-emerald-600">
            +{line}
          </div>
        )),
      ];
    })}
  </pre>
);

const MultiEditToolPart: FC<ToolPartProps> = ({ parameters, status, result }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const edits = editsParameter(parameters);

  return (
    <ToolChrome
      status={status}
      title="MultiEdit"
      argument={formatToolParameters(
        { file_path: parameters.file_path, edits: edits.length },
        { keyOrder: ["file_path", "edits"] },
      )}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t("aiChat.tool.edit.editing")}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {stringLines(result).map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="whitespace-pre-wrap">{line}</span>
            </ToolRow>
          ))}
        </ToolContent>
      ) : (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span>
              {t("aiChat.tool.multiEdit.applied")}{" "}
              <span className="font-semibold">{edits.length}</span>{" "}
              {t("aiChat.tool.multiEdit.edits")}{" "}
              <ExpandButton
                expanded={expanded}
                showKey="aiChat.tool.multiEdit.showEdits"
                hideKey="aiChat.tool.multiEdit.hideEdits"
                onClick={() => setExpanded((value) => !value)}
              />
            </span>
          </ToolRow>
          {expanded && (
            <ToolRow index={1} className="pr-2">
              <MultiEditDiffLines edits={edits} />
            </ToolRow>
          )}
        </ToolContent>
      )}
    </ToolChrome>
  );
};

const PreviewResult = ({
  status,
  preview,
  content,
  showKey = "aiChat.tool.preview.showAll",
  hideKey = "aiChat.tool.preview.showLess",
}: {
  status: ToolPartProps["status"];
  preview: React.ReactNode;
  content: string;
  showKey?: string;
  hideKey?: string;
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <ToolContent status={status}>
      <ToolRow index={0}>
        <span>
          {preview}{" "}
          <ExpandButton
            expanded={expanded}
            showKey={showKey}
            hideKey={hideKey}
            onClick={() => setExpanded((value) => !value)}
          />
        </span>
      </ToolRow>
      {expanded && (
        <ToolRow
          index={-1}
          className="mr-2 max-h-[150px] overflow-auto rounded-md border border-border p-1"
        >
          <pre>{content}</pre>
        </ToolRow>
      )}
    </ToolContent>
  );
};

const SearchToolPart: FC<ToolPartProps> = ({ parameters, status, result }) => {
  const { t } = useI18n();
  const resultText = formatResult(result) ?? "";
  const lines = resultText.split("\n").filter((line) => line.length > 0);
  const firstLine = lines[0] ?? "";
  const foundMatch = firstLine.match(/Found (\d+) files/);
  const foundCount = foundMatch?.[1] ?? String(lines.length);
  const content = foundMatch ? lines.slice(1).join("\n") : resultText;

  return (
    <ToolChrome
      status={status}
      title="Search"
      argument={formatToolParameters(parameters, {
        keyOrder: ["pattern", "path", "include"],
      })}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t("aiChat.tool.search.searching")}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {stringLines(result).map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="whitespace-pre-wrap">{line}</span>
            </ToolRow>
          ))}
        </ToolContent>
      ) : (
        <PreviewResult
          status={status}
          preview={
            <>
              {t("aiChat.tool.search.found")}{" "}
              <span className="font-semibold">{foundCount}</span>{" "}
              {t("aiChat.tool.search.files")}
            </>
          }
          content={content}
          showKey="aiChat.tool.search.showFileList"
          hideKey="aiChat.tool.search.hideFileList"
        />
      )}
    </ToolChrome>
  );
};

const LSToolPart: FC<ToolPartProps> = ({ parameters, status, result }) => {
  const { t } = useI18n();
  const lines = stringLines(result);
  const count = lines.filter((line) => line.trim().startsWith("-")).length;

  return (
    <ToolChrome
      status={status}
      title="List"
      argument={formatToolParameters(parameters, { keyOrder: ["path", "ignore"] })}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t("aiChat.tool.ls.listing")}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {lines.map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="whitespace-pre-wrap">{line}</span>
            </ToolRow>
          ))}
        </ToolContent>
      ) : (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span>
              {t("aiChat.tool.ls.listed")}{" "}
              <span className="font-semibold">{count}</span>{" "}
              {t("aiChat.tool.ls.paths")}
            </span>
          </ToolRow>
        </ToolContent>
      )}
    </ToolChrome>
  );
};

const OneLineToolPart = ({
  status,
  result,
  title,
  argument,
  pendingKey,
}: ToolPartProps & {
  title: string;
  argument: string | null;
  pendingKey: string;
}) => {
  const { t } = useI18n();

  return (
    <ToolChrome
      status={status}
      title={title}
      argument={argument}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t(pendingKey)}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          {stringLines(result).map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="whitespace-pre-wrap">{line}</span>
            </ToolRow>
          ))}
        </ToolContent>
      ) : (
        <ToolContent status={status}>
          <ToolRow index={0}>{t("aiChat.tool.preview.done")}</ToolRow>
        </ToolContent>
      )}
    </ToolChrome>
  );
};

const WebFetchToolPart: FC<ToolPartProps> = (props) => (
  <OneLineToolPart
    {...props}
    title="Fetch"
    argument={stringParameter(props.parameters, "url")}
    pendingKey="aiChat.tool.web.fetching"
  />
);

const WebSearchToolPart: FC<ToolPartProps> = (props) => (
  <OneLineToolPart
    {...props}
    title="WebSearch"
    argument={stringParameter(props.parameters, "query")}
    pendingKey="aiChat.tool.search.searching"
  />
);

const NotebookToolPart: FC<ToolPartProps> = (props) => {
  const { t } = useI18n();

  return (
    <ToolChrome
      status={props.status}
      title={props.name}
      argument={stringParameter(props.parameters, "notebook_path")}
    >
      {props.status === "pending" ? (
        <ToolContent status={props.status}>
          <ToolRow index={0}>
            <span className="animate-pulse">
              {props.name === "NotebookRead"
                ? t("aiChat.tool.read.reading")
                : t("aiChat.tool.edit.editing")}
            </span>
          </ToolRow>
        </ToolContent>
      ) : props.status === "error" ? (
        <ToolContent status={props.status}>
          {stringLines(props.result).map((line, index) => (
            <ToolRow key={`${index}-${line}`} index={index}>
              <span className="whitespace-pre-wrap">{line}</span>
            </ToolRow>
          ))}
        </ToolContent>
      ) : (
        <PreviewResult
          status={props.status}
          preview={t("aiChat.tool.preview.done")}
          content={formatResult(props.result) ?? ""}
        />
      )}
    </ToolChrome>
  );
};

const TodoReadToolPart: FC<ToolPartProps> = ({ status }) => {
  const { t } = useI18n();
  if (status !== "error") return null;
  return (
    <ToolChrome
      status={status}
      title="Read Todos"
      argument={null}
    >
      <ToolContent status={status}>
        <ToolRow index={0}>□ {t("aiChat.tool.todo.readFailed")}</ToolRow>
      </ToolContent>
    </ToolChrome>
  );
};

const TodoWriteToolPart: FC<ToolPartProps> = ({ parameters, status }) => {
  const { t } = useI18n();
  const todos = Array.isArray(parameters.todos)
    ? (parameters.todos as Array<{ content?: unknown; status?: unknown }>)
    : [];

  return (
    <ToolChrome
      status={status}
      title="Update Todos"
      argument={null}
    >
      {status === "pending" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>
            <span className="animate-pulse">{t("aiChat.tool.todo.updating")}</span>
          </ToolRow>
        </ToolContent>
      ) : status === "error" ? (
        <ToolContent status={status}>
          <ToolRow index={0}>□ {t("aiChat.tool.todo.updateFailed")}</ToolRow>
        </ToolContent>
      ) : (
        <div className="mt-1 grid min-w-0 grid-cols-[auto_auto_1fr] gap-x-1.5 overflow-hidden font-mono text-sm text-foreground">
          {todos.map((todo, index) => {
            const todoStatus = typeof todo.status === "string" ? todo.status : "";
            return (
              <Fragment key={`${index}-${String(todo.content)}`}>
                <span>{index === 0 ? "└" : " "}</span>
                <span
                  className={cn({
                    "text-muted-foreground": todoStatus === "pending",
                  })}
                >
                  {todoStatus === "completed"
                    ? "☒"
                    : todoStatus === "in_progress"
                      ? "◼"
                      : "□"}
                </span>
                <span
                  className={cn({
                    "line-through text-muted-foreground":
                      todoStatus === "completed",
                    "font-semibold": todoStatus === "in_progress",
                  })}
                >
                  {typeof todo.content === "string" ? todo.content : ""}
                </span>
              </Fragment>
            );
          })}
        </div>
      )}
    </ToolChrome>
  );
};

const NestedToolPart = ({ part }: { part: UiMessagePart }) => {
  if (part.kind !== "tool") {
    return null;
  }

  const ToolPart = resolveToolPart(part.name);
  return (
    <ToolPart
      id={part.id}
      name={part.name}
      parameters={part.parameters}
      status={part.status}
      result={"result" in part ? part.result : undefined}
      parts={part.parts}
    />
  );
};

const TaskToolPart: FC<ToolPartProps> = ({
  id,
  parameters,
  status,
  result,
  parts = [],
}) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const subagentType = stringParameter(parameters, "subagent_type");
  const title =
    subagentType && subagentType !== "general-purpose" ? subagentType : "Task";
  const description = stringParameter(parameters, "description");
  const nestedToolParts = parts.filter((part) => part.kind === "tool");

  if (nestedToolParts.length === 0) {
    return (
      <DefaultToolPart
        id={id}
        name={title}
        parameters={parameters}
        status={status}
        result={result}
        parts={parts}
      />
    );
  }

  return (
    <ToolChrome
      status={status}
      title={title}
      argument={description}
    >
      <ToolContent status={status}>
        {!expanded ? (
          <ToolRow index={0}>
            <span className="text-muted-foreground italic">
              {nestedToolParts.length} {t("aiChat.tool.task.tools")}{" "}
              <ExpandButton
                expanded={false}
                showKey="aiChat.tool.task.showAllTools"
                hideKey="aiChat.tool.task.showLessTools"
                onClick={() => setExpanded(true)}
              />
            </span>
          </ToolRow>
        ) : (
          <>
            <ToolRow index={0}>
              <span className="text-muted-foreground italic">
                {t("aiChat.tool.task.showingAllTools")}{" "}
                <ExpandButton
                  expanded
                  showKey="aiChat.tool.task.showAllTools"
                  hideKey="aiChat.tool.task.showLessTools"
                  onClick={() => setExpanded(false)}
                />
              </span>
            </ToolRow>
            {parts.map((part, index) => (
              <ToolRow key={`${part.kind}-${index}`} index={index + 1}>
                <NestedToolPart part={part} />
              </ToolRow>
            ))}
          </>
        )}
      </ToolContent>
    </ToolChrome>
  );
};

const ExitPlanModeToolPart: FC<ToolPartProps> = ({ parameters, status }) => {
  const { t } = useI18n();
  const plan = stringParameter(parameters, "plan");

  return (
    <ToolChrome
      status={status}
      title="Plan"
      argument={null}
    >
      <div className="relative group mt-1">
        <div className="space-y-3 rounded-md bg-muted/50 p-3">
          <div className="max-w-none pr-10 font-sans">
            {plan ? (
              <MarkdownContent content={plan} variant="compact" />
            ) : (
              <span className="text-muted-foreground italic">
                {t("aiChat.tool.plan.noContent")}
              </span>
            )}
          </div>
        </div>
      </div>
    </ToolChrome>
  );
};

const SuggestFollowupTaskToolPart: FC<ToolPartProps> = ({
  parameters,
  status,
}) => {
  const { t } = useI18n();
  const title = stringParameter(parameters, "title");
  const description = stringParameter(parameters, "description");

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-card p-3 sm:p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
        <div className="flex min-w-0 items-start gap-2 sm:items-baseline">
          <Sparkles
            className="mt-0.5 size-3 shrink-0 text-yellow-600 sm:mt-0"
            aria-hidden="true"
          />
          <span className="break-words text-sm font-semibold leading-tight text-foreground sm:text-base">
            {title}
          </span>
        </div>
        {status === "completed" && (
          <div className="shrink-0 self-start sm:self-auto">
            <button
              type="button"
              className="inline-flex h-8 items-center rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground hover:bg-accent sm:text-sm"
            >
              {t("aiChat.tool.followUp.start")}
              <Rocket className="ml-1 size-3.5 sm:size-4" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>
      {description && (
        <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground sm:text-sm">
          {description}
        </p>
      )}
    </div>
  );
};

const DefaultToolPart: FC<ToolPartProps> = ({
  name,
  parameters,
  status,
  result,
}) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const primary = primaryParameter(parameters);
  const formattedResult = formatResult(result);
  const hasResult =
    formattedResult !== null && formattedResult.trim().length > 0;
  const label = primary ? `${name}(${primary})` : name;
  const preview =
    status === "pending"
      ? t("aiChat.tool.preview.working")
      : status === "error"
        ? t("aiChat.tool.preview.failed")
        : t("aiChat.tool.preview.done");

  return (
    <div className="text-sm" data-status={status}>
      <div className="flex min-w-0 items-start gap-2">
        <span className="flex h-5 items-center">
          <span
            className={cn(
              "inline-block h-2 w-2 shrink-0 rounded-full",
              STATUS_CLASS_NAME[status],
            )}
            aria-hidden="true"
          />
        </span>
        <div className="min-w-0 flex-1 font-mono">
          <div className="flex min-w-0 items-center gap-1 text-left">
            <span className="line-clamp-3 min-w-0 break-words font-semibold text-foreground">
              {label}
            </span>
          </div>
          {hasResult && (
            <div className="mt-1 flex min-w-0 items-start gap-1 text-xs text-muted-foreground">
              <span aria-hidden="true">└</span>
              <span>{preview}</span>
              <button
                type="button"
                className="inline text-muted-foreground/70"
                onClick={() => setExpanded((value) => !value)}
              >
                (
                {t(
                  expanded
                    ? "aiChat.tool.preview.showLess"
                    : "aiChat.tool.preview.showAll",
                )}
                )
              </button>
            </div>
          )}
          {expanded && hasResult && (
            <div className="mt-1 pl-3 text-xs text-muted-foreground">
              <div className="max-h-[150px] overflow-auto rounded-md border border-border p-1 text-muted-foreground">
                <pre className="whitespace-pre-wrap">{formattedResult}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const TOOL_PART_REGISTRY: Record<string, FC<ToolPartProps>> = {
  Bash: BashToolPart,
  Edit: EditToolPart,
  ExitPlanMode: ExitPlanModeToolPart,
  Glob: SearchToolPart,
  Grep: SearchToolPart,
  LS: LSToolPart,
  MultiEdit: MultiEditToolPart,
  NotebookEdit: NotebookToolPart,
  NotebookRead: NotebookToolPart,
  Read: ReadToolPart,
  Task: TaskToolPart,
  TodoRead: TodoReadToolPart,
  TodoWrite: TodoWriteToolPart,
  WebFetch: WebFetchToolPart,
  WebSearch: WebSearchToolPart,
  Write: WriteToolPart,
  SuggestFollowupTask: SuggestFollowupTaskToolPart,
  mcp__terry__SuggestFollowupTask: SuggestFollowupTaskToolPart,
  mcp__aileron__ask_user_question: QuestionFormWidget,
  mcp__aileron__show_canvas_artifact: CanvasArtifactWidget,
};

export const resolveToolPart = (name: string): FC<ToolPartProps> =>
  TOOL_PART_REGISTRY[name] ?? DefaultToolPart;
