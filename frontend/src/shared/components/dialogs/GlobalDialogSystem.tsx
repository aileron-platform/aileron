/**
 * GlobalDialogSystem - 全域對話框系統
 * 
 * 渲染所有開啟的對話框
 */

import React from 'react';
import { useDialog } from '../../../app/providers/DialogProvider';

export const GlobalDialogSystem: React.FC = () => {
  const { state } = useDialog();

  return (
    <>
      {state.dialogs.map((dialog) => (
        <div key={dialog.id} className="dialog-container">
          {/* 對話框渲染邏輯將在後續實作 */}
          <div className="dialog-content">
            {dialog.content}
          </div>
        </div>
      ))}
    </>
  );
};

export default GlobalDialogSystem;
