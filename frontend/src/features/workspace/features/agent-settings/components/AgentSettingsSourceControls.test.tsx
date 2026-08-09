import { render, screen, fireEvent } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import {
  AgentSettingsLayerSelector,
  AgentSettingsSourceFilter,
  NewThreadNotice,
  sortAgentSettingsScopeValues,
} from './AgentSettingsSourceControls';

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

describe('AgentSettingsSourceControls', () => {
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

  it('orders scope values consistently for menus', () => {
    expect(sortAgentSettingsScopeValues(['local', 'plugin', 'user', 'project'])).toEqual([
      'project',
      'user',
      'local',
      'plugin',
    ]);
  });

  it('renders the localized new-thread notice', () => {
    render(<NewThreadNotice />);

    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.newThread.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.newThread.description')).toBeInTheDocument();
  });
});
