import React from 'react';
import {
  AgentSettingsLayerSelector,
  getAgentSettingsSourceIcon,
} from './SettingsSourcePrimitives';

export type CodexLayer = 'user' | 'project';

const layers: CodexLayer[] = ['user', 'project'];

export const CodexLayerSelect: React.FC<{
  value: CodexLayer;
  onChange: (value: CodexLayer) => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}> = ({ value, onChange, t }) => {
  const options = layers.map((layer) => ({
    value: layer,
    label: t(`workspace.agentSettings.codex.common.layers.${layer}`),
    icon: React.createElement(getAgentSettingsSourceIcon(layer), { className: 'h-3 w-3' }),
  }));

  return (
    <AgentSettingsLayerSelector
      value={value}
      onChange={onChange}
      options={options}
      label={t('workspace.agentSettings.codex.common.scope')}
      className="rounded-lg bg-muted/60 px-3 py-1"
    />
  );
};

export default CodexLayerSelect;
