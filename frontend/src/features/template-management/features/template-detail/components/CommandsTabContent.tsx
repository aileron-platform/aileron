import React from 'react';
import { type TemplateCommand } from '@/shared/types/templates';
import { CommandViewer } from '@/features/template-management/components/metadata-viewers/CommandViewer';
import { adaptTemplateCommands } from '@/features/template-management/components/metadata-viewers/adapters';

interface CommandsTabContentProps {
  commands?: TemplateCommand[];
}

export const CommandsTabContent: React.FC<CommandsTabContentProps> = ({ commands = [] }) => {
  // 適配數據
  const adaptedCommands = React.useMemo(() => adaptTemplateCommands(commands), [commands]);

  return (
    <CommandViewer
      items={adaptedCommands}
      isEditable={false}
    />
  );
};

export default CommandsTabContent;