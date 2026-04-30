/**
 * LSWidget - directory listing display.
 */

import React from 'react';
import { FolderOpen, Folder, FileCode, FileText, Terminal, ChevronRight } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const LSWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [expandedDirs, setExpandedDirs] = React.useState<Set<string>>(new Set());
  const path = input?.path || '';
  const content = typeof output === 'string' ? output : '';

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  // Parse the directory tree from Claude's list output.
  const parseDirectoryTree = (rawContent: string) => {
    const lines = rawContent.split('\n');
    const entries: Array<{
      path: string;
      name: string;
      type: 'file' | 'directory';
      level: number;
    }> = [];

    let currentPath: string[] = [];

    for (const line of lines) {
      // Skip NOTE section
      if (line.startsWith('NOTE:')) break;
      if (!line.trim()) continue;

      // Calculate indentation level
      const indent = line.match(/^(\s*)/)?.[1] || '';
      const level = Math.floor(indent.length / 2);

      // Extract entry name
      const entryMatch = line.match(/^\s*-\s+(.+?)(\/$)?$/);
      if (!entryMatch) continue;

      const fullName = entryMatch[1];
      const isDirectory = line.trim().endsWith('/');
      const name = fullName;

      // Update current path
      currentPath = currentPath.slice(0, level);
      currentPath.push(name);

      entries.push({
        path: currentPath.join('/'),
        name,
        type: isDirectory ? 'directory' : 'file',
        level,
      });
    }

    return entries;
  };

  const entries = parseDirectoryTree(content);

  const toggleDirectory = (dirPath: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(dirPath)) {
        next.delete(dirPath);
      } else {
        next.add(dirPath);
      }
      return next;
    });
  };

  const getChildren = (parentPath: string, parentLevel: number) => {
    return entries.filter(e => {
      if (e.level !== parentLevel + 1) return false;
      const parentParts = parentPath.split('/').filter(Boolean);
      const entryParts = e.path.split('/').filter(Boolean);

      if (entryParts.length !== parentParts.length + 1) return false;

      for (let i = 0; i < parentParts.length; i++) {
        if (parentParts[i] !== entryParts[i]) return false;
      }

      return true;
    });
  };

  const getIcon = (entry: typeof entries[0], isExpanded: boolean) => {
    if (entry.type === 'directory') {
      return isExpanded ? (
        <FolderOpen className="h-3.5 w-3.5 text-blue-500" />
      ) : (
        <Folder className="h-3.5 w-3.5 text-blue-500" />
      );
    }

    const ext = entry.name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'rs':
        return <FileCode className="h-3.5 w-3.5 text-orange-500" />;
      case 'toml':
      case 'yaml':
      case 'yml':
      case 'json':
        return <FileText className="h-3.5 w-3.5 text-yellow-500" />;
      case 'md':
        return <FileText className="h-3.5 w-3.5 text-blue-400" />;
      case 'js':
      case 'jsx':
      case 'ts':
      case 'tsx':
        return <FileCode className="h-3.5 w-3.5 text-yellow-400" />;
      case 'py':
        return <FileCode className="h-3.5 w-3.5 text-blue-500" />;
      case 'go':
        return <FileCode className="h-3.5 w-3.5 text-cyan-500" />;
      case 'sh':
      case 'bash':
        return <Terminal className="h-3.5 w-3.5 text-green-500" />;
      default:
        return <FileText className="h-3.5 w-3.5 text-gray-400" />;
    }
  };

  const renderEntry = (entry: typeof entries[0], isRoot = false): React.ReactNode => {
    const hasChildren =
      entry.type === 'directory' &&
      entries.some(e => e.path.startsWith(entry.path + '/') && e.level === entry.level + 1);
    const isExpanded = expandedDirs.has(entry.path) || isRoot;

    return (
      <div key={entry.path}>
        <div
          className={cn(
            'flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer',
            !isRoot && 'ml-4'
          )}
          onClick={() => entry.type === 'directory' && hasChildren && toggleDirectory(entry.path)}
        >
          {entry.type === 'directory' && hasChildren && (
            <ChevronRight
              className={cn(
                'h-3 w-3 text-gray-400 dark:text-zinc-500 transition-transform',
                isExpanded && 'rotate-90'
              )}
            />
          )}
          {(!hasChildren || entry.type !== 'directory') && <div className="w-3" />}
          {getIcon(entry, isExpanded)}
          <span className="text-sm font-mono text-gray-900 dark:text-zinc-100">{entry.name}</span>
        </div>

        {entry.type === 'directory' && hasChildren && isExpanded && (
          <div className="ml-2">
            {getChildren(entry.path, entry.level).map(child => renderEntry(child))}
          </div>
        )}
      </div>
    );
  };

  const rootEntries = entries.filter(e => e.level === 0);

  return (
    <div className="bg-white dark:bg-zinc-900 p-3 overflow-auto max-h-96">
      <div className="space-y-1">
        {rootEntries.map(entry => renderEntry(entry, true))}
      </div>
      {rootEntries.length === 0 && (
        <div className="text-xs text-gray-500 dark:text-zinc-400 text-center py-4">
          {t('workspace.chat.widgets.agentTools.directoryEmpty')}
        </div>
      )}
    </div>
  );
};

export default LSWidget;
