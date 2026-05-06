import React from 'react';

export const PluginCardGrid: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="grid items-stretch gap-4 md:grid-cols-2 2xl:grid-cols-3">{children}</div>
);
