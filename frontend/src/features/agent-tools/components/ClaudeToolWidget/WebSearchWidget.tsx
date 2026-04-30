/**
 * WebSearchWidget - web search display.
 */
import React from 'react';
import { ExternalLink } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const WebSearchWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();

  // Parse web search results from object or string payloads.
  const parseResults = () => {
    try {
      if (typeof output === 'object' && output !== null) {
        if (Array.isArray(output)) return output;
        if ((output as any)?.results) return (output as any).results;
      }

      if (typeof output === 'string') {
        try {
          const parsed = JSON.parse(output);
          if (Array.isArray(parsed)) return parsed;
          if (parsed?.results) return parsed.results;
        } catch {
          // Fall back to extracting a Links array from plain text.
        }

        const linksMatch = output.match(/Links:\s*(\[[\s\S]*?\])\s*(?:\n\n|$)/);
        if (linksMatch && linksMatch[1]) {
          try {
            const links = JSON.parse(linksMatch[1]);
            if (Array.isArray(links)) return links;
          } catch {
            // Ignore invalid Links JSON and return an empty list below.
          }
        }
      }
    } catch {
      // Ignore malformed tool output.
    }
    return [];
  };

  const results = parseResults();

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-zinc-900 divide-y divide-gray-100 dark:divide-zinc-800">
      {results.map((item: any, index: number) => (
        <div key={index} className="p-3 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors">
          <div className="flex items-start gap-2">
            <ExternalLink className="h-3.5 w-3.5 text-gray-400 dark:text-zinc-500 mt-1 flex-shrink-0" />
            <div className="flex-1 space-y-1">
              <a
                href={item.url || item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
              >
                {item.title}
              </a>
              {item.snippet && (
                <p className="text-xs text-gray-600 dark:text-zinc-300 line-clamp-2">
                  {item.snippet}
                </p>
              )}
              {(item.url || item.link) && (
                <p className="text-xs text-gray-400 dark:text-zinc-500 truncate">
                  {item.url || item.link}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
      {results.length === 0 && (
        <div className="p-4 text-center text-sm text-gray-500 dark:text-zinc-400">
          {t('workspace.chat.widgets.agentTools.noSearchResults')}
        </div>
      )}
    </div>
  );
};

export default WebSearchWidget;
