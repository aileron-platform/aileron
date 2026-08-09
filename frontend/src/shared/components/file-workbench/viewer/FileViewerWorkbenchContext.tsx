import React, { createContext, useContext, useMemo } from 'react';
import type { FileViewerWorkbenchContextValue } from './types';

const defaultContextValue: FileViewerWorkbenchContextValue = {
  registerFormatActions: () => undefined,
};

export const FileViewerWorkbenchContext = createContext<FileViewerWorkbenchContextValue>(defaultContextValue);

export const FileViewerWorkbenchProvider: React.FC<React.PropsWithChildren<FileViewerWorkbenchContextValue>> = ({
  children,
  registerFormatActions,
}) => {
  const value = useMemo(() => ({ registerFormatActions }), [registerFormatActions]);

  return (
    <FileViewerWorkbenchContext.Provider value={value}>
      {children}
    </FileViewerWorkbenchContext.Provider>
  );
};

export const useFileViewerWorkbench = (): FileViewerWorkbenchContextValue => useContext(FileViewerWorkbenchContext);
