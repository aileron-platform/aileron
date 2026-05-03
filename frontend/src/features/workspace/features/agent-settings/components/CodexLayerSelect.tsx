import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

export type CodexLayer = 'user' | 'project';

const layers: CodexLayer[] = ['user', 'project'];

export const CodexLayerSelect: React.FC<{
  value: CodexLayer;
  onChange: (value: CodexLayer) => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}> = ({ value, onChange, t }) => (
  <div className="flex items-center gap-2">
    <span className="text-xs text-muted-foreground">{t('workspace.agentSettings.codex.common.layer')}</span>
    <Select value={value} onValueChange={(next) => onChange(next as CodexLayer)}>
      <SelectTrigger className="h-8 w-32 text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {layers.map((layer) => (
          <SelectItem key={layer} value={layer}>
            {t(`workspace.agentSettings.codex.common.layers.${layer}`)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>
);

export default CodexLayerSelect;
