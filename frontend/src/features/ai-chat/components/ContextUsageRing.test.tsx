// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ContextUsageRing } from './ContextUsageRing';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${params.used}/${params.limit}/${params.percent}` : key,
  }),
}));

describe('ContextUsageRing', () => {
  it('renders percentage from tokens over window', () => {
    render(<ContextUsageRing contextTokens={50000} contextWindow={200000} />);

    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByTestId('context-usage-ring')).toHaveAttribute('title', 'aiChat.contextUsage.tooltip:50000/200000/25');
  });

  it('caps at 100% and switches to warning style at >=80%', () => {
    render(<ContextUsageRing contextTokens={300000} contextWindow={200000} />);

    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByTestId('context-usage-ring')).toHaveAttribute('data-warning', 'true');
  });

  it('renders nothing when window is missing or non-positive', () => {
    const { container, rerender } = render(<ContextUsageRing contextTokens={100} contextWindow={null} />);

    expect(container).toBeEmptyDOMElement();

    rerender(<ContextUsageRing contextTokens={100} contextWindow={0} />);

    expect(container).toBeEmptyDOMElement();
  });
});
