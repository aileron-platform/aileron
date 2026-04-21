import React from 'react';
import type { McpServerFormValue } from '../formTypes';
import TemplateMcpServerCard from '@/features/template-management/components/TemplateMcpServerCard';

interface McpServerCardProps {
  server: McpServerFormValue;
  showActions?: boolean;
  onEdit?: (server: McpServerFormValue) => void;
  onDelete?: (serverId: string) => void;
}

export default function McpServerCardWrapper({
  server,
  showActions = false,
  onEdit,
  onDelete
}: McpServerCardProps) {
  return (
    <TemplateMcpServerCard
      server={server}
      showActions={showActions}
      onEdit={onEdit}
      onDelete={onDelete}
    />
  );
}
