import { render, screen } from '@testing-library/react';
import { Library } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { FeatureHeader } from './FeatureHeader';

describe('FeatureHeader', () => {
  it('fills the shell header so actions can align to the far right', () => {
    render(
      <div className="flex h-10 w-full items-center">
        <FeatureHeader
          title="test.featureHeader.title"
          icon={Library}
          info={<span>test.featureHeader.info</span>}
          actions={<button type="button">test.featureHeader.action</button>}
        />
      </div>,
    );

    const heading = screen.getByRole('heading', { name: 'test.featureHeader.title' });
    expect(heading.parentElement?.parentElement).toHaveClass('w-full');
  });
});
