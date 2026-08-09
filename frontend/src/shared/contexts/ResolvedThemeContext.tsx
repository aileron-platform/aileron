import React, { createContext, useContext } from 'react';

export type ResolvedTheme = 'light' | 'dark';

const ResolvedThemeContext = createContext<ResolvedTheme>('light');

interface ResolvedThemeProviderProps {
  children: React.ReactNode;
  value: ResolvedTheme;
}

export const ResolvedThemeProvider: React.FC<ResolvedThemeProviderProps> = ({
  children,
  value,
}) => (
  <ResolvedThemeContext.Provider value={value}>
    {children}
  </ResolvedThemeContext.Provider>
);

export const useResolvedTheme = (): ResolvedTheme => useContext(ResolvedThemeContext);
