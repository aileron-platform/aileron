import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Bot,
  Cpu,
  Fingerprint,
  FolderOpen,
  Package,
  Package2,
  Puzzle,
  Settings,
  Slash,
  Sparkles,
  Star,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useI18n } from "@/shared/hooks/useI18n";
import { cn } from "@/shared/utils/cn";

interface SystemInitServer {
  name: string;
  status: string | null;
}

interface SystemInitWidgetProps {
  agentResumeId: string | null;
  model: string | null;
  cwd: string | null;
  tools: string[];
  slashCommands?: string[];
  outputStyle?: string | null;
  agents?: string[];
  skills?: string[];
  plugins?: string[];
  mcpServers: SystemInitServer[];
}

const formatMcpTool = (tool: string) => {
  const withoutPrefix = tool.replace(/^mcp__/, "");
  const [provider = "mcp", ...methodParts] = withoutPrefix.split("__");
  return {
    provider,
    method: methodParts.length > 0 ? methodParts.join("__") : withoutPrefix,
  };
};

const toolChipClassName =
  "inline-flex items-center rounded-full border border-border/70 bg-muted/40 px-2.5 py-0.5 font-mono text-[11px] leading-5 text-foreground shadow-sm";

const prefixedCommand = (command: string) =>
  command.startsWith("/") ? command : `/${command}`;

const ChipSection = ({
  icon: Icon,
  label,
  items,
  formatItem = (item) => item,
  testIdPrefix,
}: {
  icon: LucideIcon;
  label: string;
  items: string[];
  formatItem?: (item: string) => string;
  testIdPrefix: string;
}) => {
  if (items.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2 font-medium text-muted-foreground">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{label}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            data-testid={`${testIdPrefix}-${item}`}
            className={toolChipClassName}
          >
            {formatItem(item)}
          </span>
        ))}
      </div>
    </div>
  );
};

export const SystemInitWidget = ({
  agentResumeId,
  model,
  cwd,
  tools,
  slashCommands = [],
  outputStyle,
  agents = [],
  skills = [],
  plugins = [],
  mcpServers,
}: SystemInitWidgetProps) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const regularTools = tools.filter((tool) => !tool.startsWith("mcp__"));
  const mcpToolsByProvider = useMemo(
    () =>
      tools
        .filter((tool) => tool.startsWith("mcp__"))
        .reduce<Record<string, string[]>>((groups, tool) => {
          const { provider, method } = formatMcpTool(tool);
          groups[provider] = [...(groups[provider] ?? []), method];
          return groups;
        }, {}),
    [tools],
  );
  const hasRegularTools = regularTools.length > 0;
  const hasMcpTools = Object.keys(mcpToolsByProvider).length > 0;
  const hasMcpServers = mcpServers.length > 0;
  const hasTools = tools.length > 0;

  return (
    <div className="w-full" data-testid="ai-chat-system-init">
      <button
        type="button"
        className="flex w-full min-w-0 items-center gap-2 rounded-md bg-muted/40 px-3 py-2 text-left text-sm transition-colors hover:bg-muted/70"
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? (
          <ChevronDown
            className="h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
        ) : (
          <ChevronRight
            className="h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
        )}
        <Settings className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate font-medium text-foreground">
          {t("aiChat.init.title")}
        </span>
        {hasTools && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {t("aiChat.init.toolCount", { count: tools.length })}
          </span>
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-2 pt-3 text-xs text-muted-foreground">
          <div className="space-y-2">
            {agentResumeId && (
              <div className="flex min-w-0 items-center gap-2">
                <Fingerprint className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="shrink-0">{t("aiChat.init.agentResume")}</span>
                <code className="min-w-0 truncate rounded bg-background px-1.5 py-0.5 font-mono text-foreground">
                  {agentResumeId}
                </code>
              </div>
            )}
            {model && (
              <div className="flex min-w-0 items-center gap-2">
                <Cpu className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="shrink-0">{t("aiChat.init.model")}</span>
                <code className="min-w-0 truncate rounded bg-background px-1.5 py-0.5 font-mono text-foreground">
                  {model}
                </code>
              </div>
            )}
            {cwd && (
              <div className="flex min-w-0 items-center gap-2">
                <FolderOpen className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="shrink-0">{t("aiChat.init.cwd")}</span>
                <code className="min-w-0 truncate rounded bg-background px-1.5 py-0.5 font-mono text-foreground">
                  {cwd}
                </code>
              </div>
            )}
            {outputStyle && (
              <div className="flex min-w-0 items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="shrink-0">
                  {t("aiChat.init.outputStyle")}
                </span>
                <code className="min-w-0 truncate rounded bg-background px-1.5 py-0.5 font-mono text-foreground">
                  {outputStyle}
                </code>
              </div>
            )}
          </div>

          <ChipSection
            icon={Slash}
            label={t("aiChat.init.slashCommands")}
            items={slashCommands}
            formatItem={prefixedCommand}
            testIdPrefix="system-init-slash-command-chip"
          />
          <ChipSection
            icon={Bot}
            label={t("aiChat.init.agents")}
            items={agents}
            testIdPrefix="system-init-agent-chip"
          />
          <ChipSection
            icon={Star}
            label={t("aiChat.init.skills")}
            items={skills}
            testIdPrefix="system-init-skill-chip"
          />
          <ChipSection
            icon={Puzzle}
            label={t("aiChat.init.plugins")}
            items={plugins}
            testIdPrefix="system-init-plugin-chip"
          />

          {hasRegularTools && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 font-medium text-muted-foreground">
                <Wrench className="h-3.5 w-3.5" aria-hidden="true" />
                <span>{t("aiChat.init.tools")}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {regularTools.map((tool) => (
                  <span
                    key={tool}
                    data-testid={`system-init-tool-chip-${tool}`}
                    className={toolChipClassName}
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(hasMcpServers || hasMcpTools) && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 font-medium text-muted-foreground">
                <Package className="h-3.5 w-3.5" aria-hidden="true" />
                <span>{t("aiChat.init.mcpServices")}</span>
              </div>
              {hasMcpServers && (
                <div className="flex flex-wrap gap-1.5">
                  {mcpServers.map((server) => (
                    <span
                      key={server.name}
                      className={cn(toolChipClassName, "gap-1")}
                    >
                      {server.name}
                      {server.status && (
                        <span className="text-muted-foreground">
                          {server.status}
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              )}
              {Object.entries(mcpToolsByProvider).map(([provider, methods]) => (
                <div key={provider} className="space-y-1">
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <Package2 className="h-3 w-3" aria-hidden="true" />
                    <span className="font-mono font-medium">{provider}</span>
                  </div>
                  <div className={cn("flex flex-wrap gap-1.5", "pl-4")}>
                    {methods.map((method) => (
                      <span
                        key={`${provider}-${method}`}
                        data-testid={`system-init-mcp-tool-chip-${method}`}
                        className={toolChipClassName}
                      >
                        {method}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
