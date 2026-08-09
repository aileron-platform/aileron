// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ThreadStatusIcon } from './ThreadStatusIcon';

describe('ThreadStatusIcon', () => {
  it('renders spinner for working even when unread', () => {
    render(<ThreadStatusIcon status="working" unread />);

    expect(screen.getByTestId('status-active')).toBeInTheDocument();
    expect(screen.queryByTestId('status-unread')).not.toBeInTheDocument();
  });

  it('renders unread dot for complete+unread', () => {
    render(<ThreadStatusIcon status="complete" unread />);

    expect(screen.getByTestId('status-unread')).toBeInTheDocument();
  });
});
