import { useCallback, useState, useEffect } from 'react';

export type ToastVariant = 'default' | 'destructive' | 'success' | 'info';

export interface ToastOptions {
  title?: string;
  description?: string;
  variant?: ToastVariant;
}

export interface ToastItem extends ToastOptions {
  id: string;
}

export interface ToastApi {
  toast: (options: ToastOptions) => void;
}

export interface ToastState {
  toasts: ToastItem[];
  removeToast: (id: string) => void;
}

let toasts: ToastItem[] = [];
let listeners: ((toasts: ToastItem[]) => void)[] = [];

const updateListeners = () => {
  listeners.forEach(listener => listener([...toasts]));
};

const addToast = (options: ToastOptions) => {
  const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
  const toast: ToastItem = { ...options, id };

  toasts.push(toast);
  updateListeners();

  setTimeout(() => {
    removeToast(id);
  }, 5000);

  return id;
};

const removeToast = (id: string) => {
  toasts = toasts.filter(toast => toast.id !== id);
  updateListeners();
};

export const useToast = (): ToastApi => {
  const toast = useCallback((options: ToastOptions) => {
    addToast(options);
  }, []);

  return { toast };
};

export const useToastState = (): ToastState => {
  const [currentToasts, setCurrentToasts] = useState<ToastItem[]>([...toasts]);

  const subscribe = useCallback((listener: (toasts: ToastItem[]) => void) => {
    listeners.push(listener);
    return () => {
      listeners = listeners.filter(l => l !== listener);
    };
  }, []);

  useEffect(() => {
    const unsubscribe = subscribe(setCurrentToasts);
    return unsubscribe;
  }, [subscribe]);

  return {
    toasts: currentToasts,
    removeToast,
  };
};
