import React from 'react';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';

export interface KnowledgeBaseShellProps {
  children: React.ReactNode;
}

export const KnowledgeBaseShell: React.FC<KnowledgeBaseShellProps> = ({ children }) => {
  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      <GlobalNavigation />
      <div className="flex-1 overflow-hidden bg-muted/20">
        {children}
      </div>
    </div>
  );
};

export default KnowledgeBaseShell;
