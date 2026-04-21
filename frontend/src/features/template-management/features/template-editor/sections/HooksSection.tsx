import TemplateHooksSettingsWorkflow from '@/features/template-management/components/TemplateHooksSettingsWorkflow';
import type { HookFormValue } from '../formTypes';
import { useParams } from 'react-router-dom';
import { useTemplateManagementContext } from '../../../providers/TemplateManagementProvider';

interface HooksSectionProps {
  hooks: HookFormValue[];
  onHooksChange: (hooks: HookFormValue[]) => void;
}

const HooksSection: React.FC<HooksSectionProps> = ({
  hooks,
  onHooksChange
}) => {
  const { templateId } = useParams<{ templateId: string }>();
  const { reloadFromSource } = useTemplateManagementContext();

  return (
    <TemplateHooksSettingsWorkflow
      templateId={templateId}
      hooks={hooks}
      onHooksChange={onHooksChange}
      editable
      onSaveSuccess={reloadFromSource}
    />
  );
};

export default HooksSection;
