import { render, screen, fireEvent } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import {
  AgentSettingsLayerSelector,
  AgentSettingsSourceFilter,
  AgentSettingsSourceBadge,
  NewThreadNotice,
  ReadOnlySourceNotice,
  getAgentSettingsSourceBadgeClassName,
  normalizeAgentSettingsSourceType,
  sortAgentSettingsScopeValues,
} from './SettingsSourcePrimitives';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params?.source) return `${key}:${params.source}`;
      return key;
    },
  }),
}));

vi.mock('@/shared/components/file-workbench', async () => {
  const actual = await vi.importActual<typeof import('@/shared/components/file-workbench')>(
    '@/shared/components/file-workbench',
  );
  return {
    ...actual,
    ScopeSelector: ({
      value,
      onChange,
      options,
      label,
    }: {
      value: string;
      onChange: (value: string) => void;
      options: Array<{ value: string; label: string }>;
      label?: string;
    }) => (
      <label>
        {label}
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    ),
  };
});

describe('SettingsSourcePrimitives', () => {
  it('adapts layer options through the shared selector', () => {
    const onChange = vi.fn();

    render(
      <AgentSettingsLayerSelector
        value="project"
        onChange={onChange}
        label="Layer"
        options={[
          { value: 'project', label: 'Project' },
          { value: 'user', label: 'User' },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText('Layer'), { target: { value: 'user' } });

    expect(onChange).toHaveBeenCalledWith('user');
  });

  it('adapts source filter options through the shared selector', () => {
    const onChange = vi.fn();

    render(
      <AgentSettingsSourceFilter
        value="all"
        onChange={onChange}
        label="Source"
        options={[
          { value: 'all', label: 'All' },
          { value: 'project', label: 'Project' },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'project' } });

    expect(onChange).toHaveBeenCalledWith('project');
  });

  it('orders scope values consistently for menus and groups plugins with extensions', () => {
    expect(sortAgentSettingsScopeValues(['extension', 'local', 'plugin', 'user', 'project'])).toEqual([
      'project',
      'user',
      'local',
      'extension',
      'plugin',
    ]);
  });

  it('renders plugin source badges with marketplace identity', () => {
    render(
      <AgentSettingsSourceBadge
        source={{
          type: 'plugin',
          label: 'Plugin',
          pluginName: 'github',
          marketplaceName: 'openai-curated',
        }}
      />,
    );

    expect(screen.getByText('github@openai-curated')).toBeInTheDocument();
  });

  it('normalizes legacy and backend source values to shared badge styles', () => {
    expect(normalizeAgentSettingsSourceType('built-in')).toBe('built_in');
    expect(normalizeAgentSettingsSourceType('inline-config')).toBe('inline_config');
    expect(normalizeAgentSettingsSourceType('hooks_json')).toBe('hooks_json');
    expect(normalizeAgentSettingsSourceType('unknown', 'user')).toBe('user');
    expect(getAgentSettingsSourceBadgeClassName('built_in')).toContain('bg-sky-100');
    expect(getAgentSettingsSourceBadgeClassName('hooks_json')).toContain('bg-amber-100');
  });

  it('renders normalized source badges for built-in and hooks.json values', () => {
    render(
      <div>
        <AgentSettingsSourceBadge source={{ type: 'built_in', label: 'Built-in' }} />
        <AgentSettingsSourceBadge source={{ type: 'hooks_json', label: 'hooks.json' }} />
      </div>,
    );

    expect(screen.getByText('Built-in')).toBeInTheDocument();
    expect(screen.getByText('hooks.json')).toBeInTheDocument();
  });

  it('renders localized source notices', () => {
    render(
      <div>
        <ReadOnlySourceNotice sourceLabel="github@openai-curated" />
        <NewThreadNotice />
      </div>,
    );

    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.readOnly.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.readOnly.description:github@openai-curated')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.newThread.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.newThread.description')).toBeInTheDocument();
  });
});
