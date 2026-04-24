import React from 'react';
import { useParams } from 'react-router-dom';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';
import { OutputStyleViewer } from '@/shared/components/template/OutputStyleViewer';
import { adaptTemplateOutputStyles } from '@/shared/components/template/adapters';

export const OutputStyleTabContent: React.FC = () => {
  const { templateId } = useParams<{ templateId: string }>();
  const { templates, layout, setTriPrimaryOpen, setTriPrimaryWidth } = useTemplateManagementContext();

  const template = templates.find(t => t.id === templateId);

  if (!template) {
    return null;
  }

  const adaptedStyles = adaptTemplateOutputStyles(template.outputStyle || []);

  return (
    <OutputStyleViewer
      items={adaptedStyles}
      isEditable={false}
      primaryOpen={layout.triPrimaryOpen}
      onPrimaryOpenChange={setTriPrimaryOpen}
      primaryWidth={layout.triPrimaryWidth}
      onPrimaryWidthChange={setTriPrimaryWidth}
    />
  );
};

export default OutputStyleTabContent;
