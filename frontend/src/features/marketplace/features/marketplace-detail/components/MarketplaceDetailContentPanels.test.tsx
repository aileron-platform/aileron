import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplaceFeatureContentItem } from '@/features/marketplace/model/marketplaceTypes';
import { MarketplaceHooksWorkflow } from './MarketplaceDetailContentPanels';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe('MarketplaceHooksWorkflow', () => {
  it('renders Codex hook cards from marketplace package details', () => {
    const hooks: MarketplaceFeatureContentItem[] = [{
      id: 'hooks-json',
      name: 'hooks.json',
      data: {
        hooks: {
          SessionStart: [{
            matcher: '*',
            hooks: [{ type: 'command', command: 'echo ready' }],
          }],
        },
      },
    }];

    render(<MarketplaceHooksWorkflow targetClient="codex" hooks={hooks} />);

    expect(screen.getByTestId('hook-card-matcher')).toBeInTheDocument();
  });
});
