/**
 * SystemInitWidget - system initialization display.
 */

import React from 'react';
import {
  Settings,
  Fingerprint,
  Cpu,
  FolderOpen,
  Wrench,
  Package,
  Package2,
  ChevronDown,
  CheckSquare,
  Terminal,
  FolderSearch,
  Search,
  List,
  LogOut,
  FileText,
  Edit3,
  FilePlus,
  Book,
  BookOpen,
  Globe,
  ListChecks,
  ListPlus,
  Globe2,
  Slash,
  Sparkles,
  Bot,
  Star,
  Puzzle,
  type LucideIcon
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';

export interface SystemInitWidgetProps {
  sessionId?: string;
  model?: string;
  cwd?: string;
  tools?: string[];
  // Additional capability fields.
  slash_commands?: string[];
  output_style?: string;
  agents?: string[];
  skills?: string[];
  plugins?: string[];
}

export const SystemInitWidget: React.FC<SystemInitWidgetProps> = ({
  sessionId,
  model,
  cwd,
  tools = [],
  slash_commands = [],
  output_style,
  agents = [],
  skills = [],
  plugins = []
}) => {
  const [mcpExpanded, setMcpExpanded] = React.useState(false);
  const [slashCommandsExpanded, setSlashCommandsExpanded] = React.useState(false);
  const [agentsExpanded, setAgentsExpanded] = React.useState(false);
  const [skillsExpanded, setSkillsExpanded] = React.useState(false);
  const [pluginsExpanded, setPluginsExpanded] = React.useState(false);

  // Separate regular tools from MCP tools
  const regularTools = tools.filter(tool => !tool.startsWith('mcp__'));
  const mcpTools = tools.filter(tool => tool.startsWith('mcp__'));

  // Tool icon mapping
  const toolIcons: Record<string, LucideIcon> = {
    'task': CheckSquare,
    'bash': Terminal,
    'glob': FolderSearch,
    'grep': Search,
    'ls': List,
    'exit_plan_mode': LogOut,
    'read': FileText,
    'edit': Edit3,
    'multiedit': Edit3,
    'write': FilePlus,
    'notebookread': Book,
    'notebookedit': BookOpen,
    'webfetch': Globe,
    'todoread': ListChecks,
    'todowrite': ListPlus,
    'websearch': Globe2,
  };

  const getToolIcon = (toolName: string) => {
    const normalizedName = toolName.toLowerCase();
    return toolIcons[normalizedName] || Wrench;
  };

  // Format MCP tool name
  const formatMcpToolName = (toolName: string) => {
    const withoutPrefix = toolName.replace(/^mcp__/, '');
    const parts = withoutPrefix.split('__');
    if (parts.length >= 2) {
      const provider = parts[0].replace(/_/g, ' ').replace(/-/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      const method = parts.slice(1).join('__').replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      return { provider, method };
    }
    return {
      provider: 'MCP',
      method: withoutPrefix.replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ')
    };
  };

  // Group MCP tools by provider
  const mcpToolsByProvider = mcpTools.reduce((acc, tool) => {
    const { provider } = formatMcpToolName(tool);
    if (!acc[provider]) {
      acc[provider] = [];
    }
    acc[provider].push(tool);
    return acc;
  }, {} as Record<string, string[]>);

  return (
    <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
      <div className="p-4">
        <div className="flex items-start gap-3">
          <Settings className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5" />
          <div className="flex-1 space-y-4">
            <h4 className="font-semibold text-sm text-blue-900 dark:text-blue-300">System Initialized</h4>

            {/* Session Info */}
            <div className="space-y-2">
              {sessionId && (
                <div className="flex items-center gap-2 text-xs">
                  <Fingerprint className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span className="text-gray-600 dark:text-zinc-400">Session:</span>
                  <code className="font-mono text-xs bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 px-1.5 py-0.5 border border-gray-200 dark:border-zinc-700">
                    {sessionId}
                  </code>
                </div>
              )}

              {model && (
                <div className="flex items-center gap-2 text-xs">
                  <Cpu className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span className="text-gray-600 dark:text-zinc-400">Model:</span>
                  <code className="font-mono text-xs bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 px-1.5 py-0.5 border border-gray-200 dark:border-zinc-700">
                    {model}
                  </code>
                </div>
              )}

              {cwd && (
                <div className="flex items-center gap-2 text-xs">
                  <FolderOpen className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span className="text-gray-600 dark:text-zinc-400">CWD:</span>
                  <code className="font-mono text-xs bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 px-1.5 py-0.5 border border-gray-200 dark:border-zinc-700 break-all">
                    {cwd}
                  </code>
                </div>
              )}

              {/* Output Style */}
              {output_style && (
                <div className="flex items-center gap-2 text-xs">
                  <Sparkles className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span className="text-gray-600 dark:text-zinc-400">Output Style:</span>
                  <code className="font-mono text-xs bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 px-1.5 py-0.5 border border-gray-200 dark:border-zinc-700">
                    {output_style}
                  </code>
                </div>
              )}
            </div>

            {/* Slash Commands */}
            {slash_commands.length > 0 && (
              <div className="space-y-2">
                <button
                  onClick={() => setSlashCommandsExpanded(!slashCommandsExpanded)}
                  className="flex items-center gap-2 text-xs font-medium text-gray-600 hover:text-gray-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
                >
                  <Slash className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span>Slash Commands ({slash_commands.length})</span>
                  <ChevronDown className={cn(
                    "h-3 w-3 transition-transform",
                    slashCommandsExpanded && "rotate-180"
                  )} />
                </button>

                {slashCommandsExpanded && (
                  <div className="ml-5 flex flex-wrap gap-1">
                    {slash_commands.map((command, idx) => (
                      <span
                        key={idx}
                        className="text-xs py-0.5 px-2 bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700"
                      >
                        /{command}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Agents */}
            {agents.length > 0 && (
              <div className="space-y-2">
                <button
                  onClick={() => setAgentsExpanded(!agentsExpanded)}
                  className="flex items-center gap-2 text-xs font-medium text-gray-600 hover:text-gray-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
                >
                  <Bot className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span>Agents ({agents.length})</span>
                  <ChevronDown className={cn(
                    "h-3 w-3 transition-transform",
                    agentsExpanded && "rotate-180"
                  )} />
                </button>

                {agentsExpanded && (
                  <div className="ml-5 flex flex-wrap gap-1">
                    {agents.map((agent, idx) => (
                      <span
                        key={idx}
                        className="text-xs py-0.5 px-2 bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700"
                      >
                        {agent}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Skills */}
            {skills.length > 0 || (skills.length === 0 && output_style) ? (
              <div className="space-y-2">
                <button
                  onClick={() => skills.length > 0 && setSkillsExpanded(!skillsExpanded)}
                  className={cn(
                    "flex items-center gap-2 text-xs font-medium transition-colors",
                    skills.length > 0 ? "text-gray-600 hover:text-gray-900 dark:text-zinc-400 dark:hover:text-zinc-200 cursor-pointer" : "text-gray-400 dark:text-zinc-500 cursor-default"
                  )}
                  disabled={skills.length === 0}
                >
                  <Star className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span>Skills ({skills.length})</span>
                  {skills.length > 0 && (
                    <ChevronDown className={cn(
                      "h-3 w-3 transition-transform",
                      skillsExpanded && "rotate-180"
                    )} />
                  )}
                </button>

                {skillsExpanded && skills.length > 0 && (
                  <div className="ml-5 flex flex-wrap gap-1">
                    {skills.map((skill, idx) => (
                      <span
                        key={idx}
                        className="text-xs py-0.5 px-2 bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}

                {skills.length === 0 && (
                  <div className="ml-5 text-xs text-gray-400 dark:text-zinc-500 italic">
                    No skills available
                  </div>
                )}
              </div>
            ) : null}

            {/* Plugins */}
            {plugins.length > 0 || (plugins.length === 0 && output_style) ? (
              <div className="space-y-2">
                <button
                  onClick={() => plugins.length > 0 && setPluginsExpanded(!pluginsExpanded)}
                  className={cn(
                    "flex items-center gap-2 text-xs font-medium transition-colors",
                    plugins.length > 0 ? "text-gray-600 hover:text-gray-900 dark:text-zinc-400 dark:hover:text-zinc-200 cursor-pointer" : "text-gray-400 dark:text-zinc-500 cursor-default"
                  )}
                  disabled={plugins.length === 0}
                >
                  <Puzzle className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span>Plugins ({plugins.length})</span>
                  {plugins.length > 0 && (
                    <ChevronDown className={cn(
                      "h-3 w-3 transition-transform",
                      pluginsExpanded && "rotate-180"
                    )} />
                  )}
                </button>

                {pluginsExpanded && plugins.length > 0 && (
                  <div className="ml-5 flex flex-wrap gap-1">
                    {plugins.map((plugin, idx) => (
                      <span
                        key={idx}
                        className="text-xs py-0.5 px-2 bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700"
                      >
                        {plugin}
                      </span>
                    ))}
                  </div>
                )}

                {plugins.length === 0 && (
                  <div className="ml-5 text-xs text-gray-400 dark:text-zinc-500 italic">
                    No plugins available
                  </div>
                )}
              </div>
            ) : null}

            {/* Regular Tools */}
            {regularTools.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Wrench className="h-3.5 w-3.5 text-gray-500 dark:text-zinc-400" />
                  <span className="text-xs font-medium text-gray-600 dark:text-zinc-400">
                    Tools: ({regularTools.length})
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {regularTools.map((tool, idx) => {
                    const Icon = getToolIcon(tool);
                    return (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 text-xs py-0.5 px-2 bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700"
                      >
                        <Icon className="h-3 w-3" />
                        {tool}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* MCP Tools */}
            {mcpTools.length > 0 && (
              <div className="space-y-2">
                <button
                  onClick={() => setMcpExpanded(!mcpExpanded)}
                  className="flex items-center gap-2 text-xs font-medium text-gray-600 hover:text-gray-900 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
                >
                  <Package className="h-3.5 w-3.5" />
                  <span>MCP Services ({mcpTools.length})</span>
                  <ChevronDown className={cn(
                    "h-3 w-3 transition-transform",
                    mcpExpanded && "rotate-180"
                  )} />
                </button>

                {mcpExpanded && (
                  <div className="ml-5 space-y-3">
                    {Object.entries(mcpToolsByProvider).map(([provider, providerTools]) => (
                      <div key={provider} className="space-y-1.5">
                        <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-zinc-400">
                          <Package2 className="h-3 w-3" />
                          <span className="font-medium">{provider}</span>
                          <span className="text-gray-400 dark:text-zinc-500">({providerTools.length})</span>
                        </div>
                        <div className="ml-4 flex flex-wrap gap-1">
                          {providerTools.map((tool, idx) => {
                            const { method } = formatMcpToolName(tool);
                            return (
                              <span
                                key={idx}
                                className="text-xs py-0 px-1.5 bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700"
                              >
                                {method}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {tools.length === 0 && (
              <div className="text-xs text-gray-500 dark:text-zinc-400 italic">
                No tools available
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemInitWidget;
