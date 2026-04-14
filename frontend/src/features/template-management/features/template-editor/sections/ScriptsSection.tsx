import React from 'react';
import { FileCode } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import TemplateFileManager from './TemplateFileManager';
import type { FileEntryFormValue } from '../formTypes';

interface ScriptsSectionProps {
  scripts: FileEntryFormValue[];
  onScriptsChange: (scripts: FileEntryFormValue[]) => void;
  templateId?: string;
}

const ScriptsSection: React.FC<ScriptsSectionProps> = ({ scripts, onScriptsChange, templateId }) => {
  const { t } = useI18n();

  return (
    <TemplateFileManager
      templateId={templateId}
      basePath="scripts"
      title={t('template.editor.tabs.scripts')}
      leadingIcon={<FileCode className="h-4 w-4 text-primary" />}
      onFilesChange={(files) => {
        // 轉換 FileNode[] 為 FileEntryFormValue[]
        const scriptFiles: FileEntryFormValue[] = files
          .filter(f => f.type === 'file')
          .map(f => ({
            localId: `local-${Math.random().toString(36).slice(2, 10)}`,
            fileName: f.name,
            content: f.content || '',
            path: f.path,
          }));
        onScriptsChange(scriptFiles);
      }}
    />
  );
};

export default ScriptsSection;
