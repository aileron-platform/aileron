import React from 'react';
import { Wand2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import TemplateFileManager from './TemplateFileManager';
import type { SkillFileFormValue } from '../formTypes';

interface SkillsSectionProps {
  skills: SkillFileFormValue[];
  onSkillsChange: (skills: SkillFileFormValue[]) => void;
  templateId?: string;
}

const SkillsSection: React.FC<SkillsSectionProps> = ({ skills, onSkillsChange, templateId }) => {
  const { t } = useI18n();

  return (
    <TemplateFileManager
      templateId={templateId}
      basePath="skills"
      title={t('template.editor.tabs.skills')}
      leadingIcon={<Wand2 className="h-4 w-4 text-primary" />}
      onFilesChange={(files) => {
        // 轉換 FileNode[] 為 SkillFileFormValue[]
        const skillFiles: SkillFileFormValue[] = files
          .filter(f => f.type === 'file')
          .map(f => ({
            localId: `local-${Math.random().toString(36).slice(2, 10)}`,
            fileName: f.name,
            content: f.content || '',
            path: f.path,
          }));
        onSkillsChange(skillFiles);
      }}
    />
  );
};

export default SkillsSection;
