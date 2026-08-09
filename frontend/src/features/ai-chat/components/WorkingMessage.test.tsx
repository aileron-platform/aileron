// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkingMessage } from './WorkingMessage';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe('WorkingMessage', () => {
  it('shows i18n working copy per running status', () => {
    render(<WorkingMessage status="booting" />);

    expect(screen.getByText('aiChat.working.booting')).toBeInTheDocument();
  });

  it('renders nothing when complete', () => {
    const { container } = render(<WorkingMessage status="complete" />);

    expect(container).toBeEmptyDOMElement();
  });
});
