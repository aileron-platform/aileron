import React from 'react';
import TemplateMcpSettingsWorkflow from '@/features/template-management/components/TemplateMcpSettingsWorkflow';
import type { TemplateMcpServer } from '@/shared/types/templates';
import { mapTemplateMcpServersToFormValues } from '../../template-editor/hooks/templateSettingsAdapters';

interface McpTabContentProps {
  mcpServers?: TemplateMcpServer[];
}

export const McpTabContent: React.FC<McpTabContentProps> = ({ mcpServers = [] }) => {
  const formServers = mapTemplateMcpServersToFormValues(mcpServers);

  return <TemplateMcpSettingsWorkflow servers={formServers} />;
};

export default McpTabContent;
