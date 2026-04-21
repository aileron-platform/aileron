import React from 'react';
import TemplateHooksSettingsWorkflow from '@/features/template-management/components/TemplateHooksSettingsWorkflow';
import { type TemplateHook } from '@/shared/types/templates';
import { mapTemplateHooksToFormValues } from '../../template-editor/hooks/templateSettingsAdapters';

interface HooksTabContentProps {
  hooks?: TemplateHook[];
}

export const HooksTabContent: React.FC<HooksTabContentProps> = ({ hooks = [] }) => {
  const formHooks = mapTemplateHooksToFormValues(hooks);

  return <TemplateHooksSettingsWorkflow hooks={formHooks} />;
};

export default HooksTabContent;
