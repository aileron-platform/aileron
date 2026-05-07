import React from 'react';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';

export interface MarketplaceShellProps {
  children: React.ReactNode;
}

export const MarketplaceShell: React.FC<MarketplaceShellProps> = ({ children }) => {
  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      <GlobalNavigation />
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-hidden bg-muted/20">
          {children}
        </div>
      </div>
    </div>
  );
};

export default MarketplaceShell;
