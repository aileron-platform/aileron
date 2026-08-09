import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it } from 'vitest';
import {
  DocumentSourceBadge,
  getDocumentSourceBadgeClassName,
  getDocumentSourceIcon,
  normalizeDocumentSourceType,
} from './DocumentSourceBadge';

describe('DocumentSourceBadge', () => {
  it('renders plugin sources with marketplace identity', () => {
    render(
      <DocumentSourceBadge
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

  it('normalizes canonical source values and falls back for unknown values', () => {
    expect(normalizeDocumentSourceType('hooks_json')).toBe('hooks_json');
    expect(normalizeDocumentSourceType('unknown', 'user')).toBe('user');
    expect(getDocumentSourceBadgeClassName('built_in')).toContain('bg-sky-100');
    expect(getDocumentSourceBadgeClassName('hooks_json')).toContain('bg-amber-100');
    expect(getDocumentSourceIcon('unknown')).toBe(getDocumentSourceIcon('project'));
  });

  it('renders canonical built-in and hooks.json source badges', () => {
    render(
      <div>
        <DocumentSourceBadge source={{ type: 'built_in', label: 'Built-in' }} />
        <DocumentSourceBadge source={{ type: 'hooks_json', label: 'hooks.json' }} />
      </div>,
    );

    expect(screen.getByText('Built-in')).toBeInTheDocument();
    expect(screen.getByText('hooks.json')).toBeInTheDocument();
  });
});
