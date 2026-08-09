import React from 'react';

interface MarketplaceInfoGridRowProps {
  label: string;
  value: React.ReactNode;
  monospace?: boolean;
}

export const MarketplaceInfoGridRow: React.FC<MarketplaceInfoGridRowProps> = ({
  label,
  value,
  monospace = false,
}) => (
  <div className="grid grid-cols-3 gap-4">
    <div className="text-sm font-medium text-muted-foreground">{label}</div>
    <div className={`col-span-2 break-words text-sm text-foreground ${monospace ? 'font-mono' : ''}`}>{value}</div>
  </div>
);
