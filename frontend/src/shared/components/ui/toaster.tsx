import React from 'react';
import { Toast, ToastProps } from './toast';
import { useToastState } from './use-toast';

export const Toaster: React.FC = () => {
  const { toasts, removeToast } = useToastState();

  return (
    <div className="pointer-events-none fixed top-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          {...toast}
          onClose={removeToast}
        />
      ))}
    </div>
  );
};