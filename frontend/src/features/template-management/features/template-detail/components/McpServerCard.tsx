import React from 'react';
import type { ClaudeMcpServer } from '@/features/workspace/features/claude-code/data';
import McpServerCard, { type BaseMcpServerData } from '@/features/template-management/components/McpServerCard';

interface McpServerCardProps {
  server: ClaudeMcpServer;
  onCopyConfig: (server: ClaudeMcpServer) => void;
}

const McpServerCardWrapper: React.FC<McpServerCardProps> = ({ server, onCopyConfig }) => {
  return (
    <McpServerCard<ClaudeMcpServer>
      server={server}
      mode="view"
      onCopyConfig={onCopyConfig}
    />
  );
};

export default McpServerCardWrapper;

