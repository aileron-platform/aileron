/**
 */

import React from 'react';
import { FileEditor } from './components/FileEditor';

export const FileManagementPage: React.FC = () => {
  return (
    <div className="h-full flex flex-col bg-background">
      <div className="flex-1 overflow-hidden">
        <FileEditor />
      </div>
    </div>
  );
};

export default FileManagementPage;
