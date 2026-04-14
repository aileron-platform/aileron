/**
 * FileManagementFeature - 檔案管理功能
 * 第三欄編輯器區域，不顯示 FeatureHeader
 */

import React from 'react';
import { FileEditor } from './components/FileEditor';

export const FileManagementFeature: React.FC = () => {
  return (
    <div className="h-full flex flex-col bg-background">
      {/* 檔案編輯器內容 - 佔滿整個區域 */}
      <div className="flex-1 overflow-hidden">
        <FileEditor />
      </div>
    </div>
  );
};

export default FileManagementFeature;
