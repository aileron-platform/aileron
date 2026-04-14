/**
 * AgentWidget - 子代理執行
 */
import React from 'react';
import { Bot, Cpu, Wrench, Timer, Hash, Maximize2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/shared/utils/cn';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

/** 從 tool_result 的第二個 text block 解析 usage 資訊 */
function parseUsageMetadata(raw: string): {
  agentId?: string;
  totalTokens?: number;
  toolUses?: number;
  durationMs?: number;
} {
  const result: ReturnType<typeof parseUsageMetadata> = {};
  const agentIdMatch = raw.match(/agentId:\s*(\S+)/);
  if (agentIdMatch) result.agentId = agentIdMatch[1];
  const tokensMatch = raw.match(/total_tokens:\s*(\d+)/);
  if (tokensMatch) result.totalTokens = parseInt(tokensMatch[1], 10);
  const toolUsesMatch = raw.match(/tool_uses:\s*(\d+)/);
  if (toolUsesMatch) result.toolUses = parseInt(toolUsesMatch[1], 10);
  const durationMatch = raw.match(/duration_ms:\s*(\d+)/);
  if (durationMatch) result.durationMs = parseInt(durationMatch[1], 10);
  return result;
}

/** 格式化持續時間 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const min = Math.floor(sec / 60);
  const remainSec = Math.round(sec % 60);
  return `${min}m ${remainSec}s`;
}

const agentTypeColors: Record<string, string> = {
  'general-purpose': 'bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300',
  'Explore': 'bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300',
  'Plan': 'bg-violet-100 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300',
};

export const AgentWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const description = input?.description || '';
  const prompt = input?.prompt || '';
  const subagentType = input?.subagent_type || 'general-purpose';
  const model = input?.model;
  const runInBackground = input?.run_in_background;
  const isolation = input?.isolation;

  // output 可能是 string 或 array of text blocks
  const { resultContent, metadata } = React.useMemo(() => {
    let texts: string[] = [];

    if (typeof output === 'string') {
      // 嘗試解析 JSON array
      try {
        const parsed = JSON.parse(output);
        if (Array.isArray(parsed)) {
          texts = parsed.map((item: any) => item?.text || '').filter(Boolean);
        } else {
          texts = [output];
        }
      } catch {
        texts = [output];
      }
    } else if (Array.isArray(output)) {
      texts = (output as any[]).map((item: any) => item?.text || '').filter(Boolean);
    } else if (output && typeof output === 'object') {
      texts = [JSON.stringify(output, null, 2)];
    }

    // 最後一個 text block 通常包含 agentId 和 usage
    let meta: ReturnType<typeof parseUsageMetadata> = {};
    let contentTexts = texts;

    if (texts.length >= 2) {
      const lastText = texts[texts.length - 1];
      if (lastText.includes('agentId:') || lastText.includes('<usage>')) {
        meta = parseUsageMetadata(lastText);
        contentTexts = texts.slice(0, -1);
      }
    } else if (texts.length === 1) {
      // 單一 text block 可能同時包含內容和 metadata
      const text = texts[0];
      const usageIdx = text.indexOf('\nagentId:');
      if (usageIdx !== -1) {
        meta = parseUsageMetadata(text.substring(usageIdx));
        contentTexts = [text.substring(0, usageIdx).trim()];
      }
    }

    return { resultContent: contentTexts.join('\n\n'), metadata: meta };
  }, [output]);

  const lines = resultContent.split('\n');
  const PREVIEW_LINES = 12;
  const previewContent = lines.slice(0, PREVIEW_LINES).join('\n');
  const hasMoreContent = lines.length > PREVIEW_LINES;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-white dark:bg-zinc-900">
        {/* Agent 資訊列 */}
        <div className="px-3 pt-3 pb-2 flex items-center gap-1.5 flex-wrap">
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded font-medium',
            agentTypeColors[subagentType] || 'bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-zinc-300'
          )}>
            {subagentType}
          </span>
          {model && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300">
              <Cpu className="h-3 w-3 inline mr-0.5 -mt-px" />
              {model}
            </span>
          )}
          {runInBackground && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-zinc-800 text-gray-500 dark:text-zinc-400">
              背景執行
            </span>
          )}
          {isolation === 'worktree' && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-zinc-800 text-gray-500 dark:text-zinc-400">
              worktree
            </span>
          )}
        </div>

        {/* 描述 */}
        {description && (
          <div className="px-3 pb-2">
            <p className="text-xs text-gray-700 dark:text-zinc-200">{description}</p>
          </div>
        )}

        {/* 結果內容 */}
        {resultContent && (
          <div className="px-3 pb-3 border-t border-gray-100 dark:border-zinc-800 pt-2">
            <div className="prose prose-sm dark:prose-invert max-w-none text-xs text-gray-900 dark:text-zinc-100 overflow-x-auto max-h-64 overflow-y-auto">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {previewContent || '無結果'}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {/* Usage 統計 + 展開按鈕 */}
        {(metadata.totalTokens || metadata.toolUses !== undefined || metadata.durationMs || hasMoreContent) && (
          <div className="px-3 py-1.5 bg-gray-50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 flex items-center gap-3 flex-wrap">
            {/* Usage 統計 */}
            <div className="flex items-center gap-3 text-xs text-gray-400 dark:text-zinc-500">
              {metadata.totalTokens !== undefined && (
                <span className="inline-flex items-center gap-0.5" title="Tokens">
                  <Hash className="h-3 w-3" />
                  {metadata.totalTokens.toLocaleString()}
                </span>
              )}
              {metadata.toolUses !== undefined && (
                <span className="inline-flex items-center gap-0.5" title="Tool calls">
                  <Wrench className="h-3 w-3" />
                  {metadata.toolUses}
                </span>
              )}
              {metadata.durationMs !== undefined && (
                <span className="inline-flex items-center gap-0.5" title="Duration">
                  <Timer className="h-3 w-3" />
                  {formatDuration(metadata.durationMs)}
                </span>
              )}
            </div>

            {/* 展開完整內容按鈕 */}
            {hasMoreContent && (
              <button
                onClick={() => setShowFullscreen(true)}
                className="ml-auto text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
              >
                <Maximize2 className="h-3 w-3" />
                查看完整內容 ({lines.length} 行)
              </button>
            )}
          </div>
        )}
      </div>

      {/* 全螢幕對話框 */}
      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <Bot className="h-4 w-4" />
              <span className="truncate">{description || `Agent (${subagentType})`}</span>
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-white dark:bg-zinc-900 rounded p-6">
            <div className="prose prose-sm dark:prose-invert max-w-none text-gray-900 dark:text-zinc-100">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {resultContent || '無結果'}
              </ReactMarkdown>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default AgentWidget;
