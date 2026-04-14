import React from 'react';
import { type TemplateSlashCommand } from '@/shared/types/templates';
import { SlashCommandViewer } from '@/shared/components/template/SlashCommandViewer';
import { adaptTemplateSlashCommands } from '@/shared/components/template/adapters';

interface SlashCommandsTabContentProps {
  commands?: TemplateSlashCommand[];
}

export const SlashCommandsTabContent: React.FC<SlashCommandsTabContentProps> = ({ commands = [] }) => {
  // 適配數據
  const adaptedCommands = React.useMemo(() => adaptTemplateSlashCommands(commands), [commands]);

  return (
    <SlashCommandViewer
      items={adaptedCommands}
      isEditable={false}
    />
  );
};

export default SlashCommandsTabContent;