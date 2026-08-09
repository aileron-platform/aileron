/**
 * 
 */

import React, { createContext, useContext, useReducer, ReactNode } from 'react';

export interface DialogConfig {
  id: string;
  type: 'modal' | 'drawer' | 'popover';
  title?: string;
  content: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  closable?: boolean;
  maskClosable?: boolean;
  onClose?: () => void;
  onConfirm?: () => void;
  onCancel?: () => void;
  footer?: ReactNode;
  className?: string;
  zIndex?: number;
}

export interface DialogState {
  dialogs: DialogConfig[];
  activeDialogId: string | null;
  queue: string[];
}

export type DialogAction =
  | { type: 'OPEN_DIALOG'; payload: DialogConfig }
  | { type: 'CLOSE_DIALOG'; payload: string }
  | { type: 'CLOSE_ALL_DIALOGS' }
  | { type: 'SET_ACTIVE_DIALOG'; payload: string | null }
  | { type: 'UPDATE_DIALOG'; payload: { id: string; updates: Partial<DialogConfig> } };

const initialState: DialogState = {
  dialogs: [],
  activeDialogId: null,
  queue: [],
};

const dialogReducer = (state: DialogState, action: DialogAction): DialogState => {
  switch (action.type) {
    case 'OPEN_DIALOG':
      const newDialog = action.payload;
      return {
        ...state,
        dialogs: [...state.dialogs, newDialog],
        activeDialogId: newDialog.id,
        queue: [...state.queue, newDialog.id],
      };
      
    case 'CLOSE_DIALOG':
      const dialogId = action.payload;
      const updatedDialogs = state.dialogs.filter(d => d.id !== dialogId);
      const updatedQueue = state.queue.filter(id => id !== dialogId);
      const newActiveId = updatedQueue.length > 0 ? updatedQueue[updatedQueue.length - 1] : null;
      
      return {
        ...state,
        dialogs: updatedDialogs,
        activeDialogId: newActiveId,
        queue: updatedQueue,
      };
      
    case 'CLOSE_ALL_DIALOGS':
      return {
        ...state,
        dialogs: [],
        activeDialogId: null,
        queue: [],
      };
      
    case 'SET_ACTIVE_DIALOG':
      return {
        ...state,
        activeDialogId: action.payload,
      };
      
    case 'UPDATE_DIALOG':
      const { id, updates } = action.payload;
      return {
        ...state,
        dialogs: state.dialogs.map(dialog =>
          dialog.id === id ? { ...dialog, ...updates } : dialog
        ),
      };
      
    default:
      return state;
  }
};

interface DialogContextType {
  state: DialogState;
  dispatch: React.Dispatch<DialogAction>;
  openDialog: (config: Omit<DialogConfig, 'id'>) => string;
  closeDialog: (id: string) => void;
  closeAllDialogs: () => void;
  updateDialog: (id: string, updates: Partial<DialogConfig>) => void;
}

const DialogContext = createContext<DialogContextType | undefined>(undefined);

interface DialogProviderProps {
  children: ReactNode;
}

export const DialogProvider: React.FC<DialogProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(dialogReducer, initialState);

  const openDialog = (config: Omit<DialogConfig, 'id'>): string => {
    const id = `dialog-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const dialogConfig: DialogConfig = {
      ...config,
      id,
      closable: config.closable ?? true,
      maskClosable: config.maskClosable ?? true,
      size: config.size ?? 'md',
      type: config.type ?? 'modal',
    };
    
    dispatch({ type: 'OPEN_DIALOG', payload: dialogConfig });
    return id;
  };

  const closeDialog = (id: string) => {
    const dialog = state.dialogs.find(d => d.id === id);
    if (dialog?.onClose) {
      dialog.onClose();
    }
    dispatch({ type: 'CLOSE_DIALOG', payload: id });
  };

  const closeAllDialogs = () => {
    state.dialogs.forEach(dialog => {
      if (dialog.onClose) {
        dialog.onClose();
      }
    });
    dispatch({ type: 'CLOSE_ALL_DIALOGS' });
  };

  const updateDialog = (id: string, updates: Partial<DialogConfig>) => {
    dispatch({ type: 'UPDATE_DIALOG', payload: { id, updates } });
  };

  const contextValue: DialogContextType = {
    state,
    dispatch,
    openDialog,
    closeDialog,
    closeAllDialogs,
    updateDialog,
  };

  return (
    <DialogContext.Provider value={contextValue}>
      {children}
    </DialogContext.Provider>
  );
};

// Hook for using dialog context
export const useDialog = (): DialogContextType => {
  const context = useContext(DialogContext);
  if (context === undefined) {
    throw new Error('useDialog must be used within a DialogProvider');
  }
  return context;
};

export default DialogProvider;
