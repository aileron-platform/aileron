/**
 * Agentic Tool 選擇器
 *
 * 提供選擇不同 AI Coding CLI 工具的介面
 */

import React, { useCallback, useState } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/shared/utils/cn';
import type { AgenticTool, ToolCapabilities } from './agentSessionTypes';

// 工具圖標映射
const TOOL_ICONS: Record<AgenticTool, string> = {
  'claude-code': '🤖',
  codex: '🔮',
  gemini: '💎',
  opencode: '🛠️',
};

// 工具顯示名稱
const TOOL_NAMES: Record<AgenticTool, string> = {
  'claude-code': 'Claude Code',
  codex: 'Codex',
  gemini: 'Gemini',
  opencode: 'OpenCode',
};

// 預設工具能力（當 API 無法取得時使用）
const DEFAULT_CAPABILITIES: Record<AgenticTool, ToolCapabilities> = {
  'claude-code': {
    name: 'Claude Code',
    streaming: true,
    thinking: true,
    multimodal: true,
    max_context_window: 200000,
    prompt_caching: true,
    local_execution: false,
    built_in_tools: ['read_file', 'write_file', 'edit_file', 'bash', 'grep', 'glob', 'task'],
  },
  codex: {
    name: 'Codex',
    streaming: true,
    thinking: false,
    multimodal: false,
    max_context_window: 200000,
    prompt_caching: false,
    local_execution: false,
    built_in_tools: ['shell', 'file_read', 'file_write', 'apply_patch'],
  },
  gemini: {
    name: 'Gemini',
    streaming: true,
    thinking: false,
    multimodal: true,
    max_context_window: 1000000,
    prompt_caching: false,
    local_execution: false,
    built_in_tools: ['code_execution', 'file_search', 'web_search'],
  },
  opencode: {
    name: 'OpenCode',
    streaming: false,
    thinking: false,
    multimodal: false,
    max_context_window: 128000,
    prompt_caching: false,
    local_execution: true,
    built_in_tools: ['shell', 'read_file', 'write_file'],
  },
};

interface AgenticToolSelectorProps {
  value: AgenticTool;
  onChange: (tool: AgenticTool) => void;
  capabilities?: Record<AgenticTool, ToolCapabilities>;
  disabled?: boolean;
  className?: string;
}

export const AgenticToolSelector: React.FC<AgenticToolSelectorProps> = ({
  value,
  onChange,
  capabilities,
  disabled = false,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  // 確保 capabilities 不為 null 或 undefined，使用預設值
  const safeCapabilities = capabilities ?? DEFAULT_CAPABILITIES;

  const handleChange = useCallback(
    (newValue: string) => {
      onChange(newValue as AgenticTool);
    },
    [onChange]
  );

  const currentCaps = safeCapabilities[value] || DEFAULT_CAPABILITIES[value];

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <TooltipProvider>
        <Select
          value={value}
          onValueChange={handleChange}
          disabled={disabled}
          open={isOpen}
          onOpenChange={setIsOpen}
        >
          <SelectTrigger className="w-[180px] h-8">
            <SelectValue>
              <div className="flex items-center gap-2">
                <span>{TOOL_ICONS[value]}</span>
                <span>{TOOL_NAMES[value]}</span>
              </div>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(TOOL_NAMES) as AgenticTool[]).map((tool) => {
              const caps = safeCapabilities[tool] || DEFAULT_CAPABILITIES[tool];
              return (
                <Tooltip key={tool}>
                  <TooltipTrigger asChild>
                    <SelectItem value={tool} className="cursor-pointer">
                      <div className="flex items-center gap-2">
                        <span>{TOOL_ICONS[tool]}</span>
                        <span>{TOOL_NAMES[tool]}</span>
                        <div className="flex gap-1 ml-2">
                          {caps.thinking && (
                            <Badge variant="secondary" className="text-[10px] px-1 py-0">
                              🧠
                            </Badge>
                          )}
                          {caps.multimodal && (
                            <Badge variant="secondary" className="text-[10px] px-1 py-0">
                              🖼️
                            </Badge>
                          )}
                          {caps.local_execution && (
                            <Badge variant="secondary" className="text-[10px] px-1 py-0">
                              💻
                            </Badge>
                          )}
                        </div>
                      </div>
                    </SelectItem>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[300px]">
                    <ToolCapabilitiesPopover capabilities={caps} />
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </SelectContent>
        </Select>

        {/* 當前工具能力指示 */}
        <div className="flex items-center gap-1">
          {currentCaps.streaming && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0.5">
                  串流
                </Badge>
              </TooltipTrigger>
              <TooltipContent>支援串流回應</TooltipContent>
            </Tooltip>
          )}
          {currentCaps.thinking && (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0.5">
                  思考
                </Badge>
              </TooltipTrigger>
              <TooltipContent>支援 Extended Thinking Mode</TooltipContent>
            </Tooltip>
          )}
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0.5">
                {formatContextWindow(currentCaps.max_context_window)}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              最大 Context Window: {currentCaps.max_context_window.toLocaleString()} tokens
            </TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>
    </div>
  );
};

interface ToolCapabilitiesPopoverProps {
  capabilities: ToolCapabilities;
}

const ToolCapabilitiesPopover: React.FC<ToolCapabilitiesPopoverProps> = ({ capabilities }) => {
  return (
    <div className="space-y-2 p-1">
      <div className="font-semibold">{capabilities.name}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex items-center gap-1">
          <span className={capabilities.streaming ? 'text-green-500' : 'text-gray-400'}>
            {capabilities.streaming ? '✓' : '✗'}
          </span>
          <span>串流回應</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={capabilities.thinking ? 'text-green-500' : 'text-gray-400'}>
            {capabilities.thinking ? '✓' : '✗'}
          </span>
          <span>思考模式</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={capabilities.multimodal ? 'text-green-500' : 'text-gray-400'}>
            {capabilities.multimodal ? '✓' : '✗'}
          </span>
          <span>多模態</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={capabilities.prompt_caching ? 'text-green-500' : 'text-gray-400'}>
            {capabilities.prompt_caching ? '✓' : '✗'}
          </span>
          <span>Prompt 快取</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={capabilities.local_execution ? 'text-green-500' : 'text-gray-400'}>
            {capabilities.local_execution ? '✓' : '✗'}
          </span>
          <span>本地執行</span>
        </div>
        <div className="col-span-2">
          <span className="text-muted-foreground">
            Context: {formatContextWindow(capabilities.max_context_window)}
          </span>
        </div>
      </div>
      {capabilities.built_in_tools.length > 0 && (
        <div className="border-t pt-1 mt-1">
          <div className="text-xs text-muted-foreground">內建工具：</div>
          <div className="flex flex-wrap gap-1 mt-1">
            {capabilities.built_in_tools.slice(0, 5).map((tool) => (
              <Badge key={tool} variant="secondary" className="text-[10px]">
                {tool}
              </Badge>
            ))}
            {capabilities.built_in_tools.length > 5 && (
              <Badge variant="secondary" className="text-[10px]">
                +{capabilities.built_in_tools.length - 5}
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

function formatContextWindow(tokens: number): string {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(0)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(0)}K`;
  }
  return String(tokens);
}

export default AgenticToolSelector;
