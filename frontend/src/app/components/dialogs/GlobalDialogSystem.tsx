import React from 'react';
import { useDialog } from '@/app/providers/DialogProvider';

export const GlobalDialogSystem: React.FC = () => {
  const { state } = useDialog();

  return (
    <>
      {state.dialogs.map((dialog) => (
        <div key={dialog.id} className="dialog-container">
          <div className="dialog-content">
            {dialog.content}
          </div>
        </div>
      ))}
    </>
  );
};

export default GlobalDialogSystem;
