/**
 * SkillWidget - 技能執行
 */
import React from 'react';
import { Award } from 'lucide-react';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const SkillWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const skillName = input?.skill || '';
  const args = input?.args;
  const content = typeof output === 'string' ? output : '';

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-zinc-900">
      {/* 技能資訊 */}
      <div className="p-3 flex items-center gap-2">
        <Award className="h-4 w-4 text-amber-500 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono font-medium text-gray-900 dark:text-zinc-100">
              /{skillName}
            </code>
            {args && (
              <span className="text-xs text-gray-500 dark:text-zinc-400 truncate">
                {args}
              </span>
            )}
          </div>
          {content && (
            <p className="text-xs text-gray-600 dark:text-zinc-300 mt-1">
              {content}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default SkillWidget;
