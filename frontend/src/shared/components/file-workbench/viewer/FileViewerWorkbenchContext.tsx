import React, { createContext, useContext } from 'react';
import type { FileViewerWorkbenchContextValue } from './types';

const defaultContextValue: FileViewerWorkbenchContextValue = {
  registerFormatActions: () => undefined,
};

export const FileViewerWorkbenchContext = createContext<FileViewerWorkbenchContextValue>(defaultContextValue);

export const FileViewerWorkbenchProvider: React.FC<React.PropsWithChildren<FileViewerWorkbenchContextValue>> = ({
  children,
  registerFormatActions,
}) => (
  <FileViewerWorkbenchContext.Provider value={{ registerFormatActions }}>
    {children}
  </FileViewerWorkbenchContext.Provider>
);

export const useFileViewerWorkbench = (): FileViewerWorkbenchContextValue => useContext(FileViewerWorkbenchContext);
