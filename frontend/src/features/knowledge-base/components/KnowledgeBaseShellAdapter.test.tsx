import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Database } from 'lucide-react';
import type { ProductShellProps } from '@/shared/components/shell';
import { KnowledgeBaseShellAdapter } from './KnowledgeBaseShellAdapter';

const productShellMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/components/shell', () => ({
  ProductShell: (props: ProductShellProps) => {
    productShellMock(props);
    const { body } = props;
    return (
      <div data-testid="product-shell">
        <div data-testid="product-shell-top-bar">{props.topBar}</div>
        <div data-testid="product-shell-header">{props.header}</div>
        {body.kind === 'state' ? (
          <div data-testid="product-shell-state">{body.content}</div>
        ) : (
          <>
            <div data-testid="product-shell-navigation">
              {body.navigation?.content({ collapsed: false })}
            </div>
            <div data-testid="product-shell-navigator">
              {body.navigator?.content({ collapsed: false })}
            </div>
            <div data-testid="product-shell-main">{body.main.content}</div>
          </>
        )}
      </div>
    );
  },
}));

describe('KnowledgeBaseShellAdapter', () => {
  it('maps semantic regions into ProductShell without owning page geometry', () => {
    render(
      <KnowledgeBaseShellAdapter
        navigationSlot={<div>global navigation</div>}
        surface={{
          kind: 'regions',
          header: <div>knowledge base header</div>,
          navigation: {
            accessibleLabel: 'knowledge base navigation',
            title: 'Knowledge Base',
            content: <div>navigation content</div>,
          },
          navigator: {
            accessibleLabel: 'file navigator',
            title: 'Files',
            icon: Database,
            content: ({ collapsed }) => <div>{collapsed ? 'collapsed navigator' : 'navigator content'}</div>,
          },
          main: {
            accessibleLabel: 'knowledge base main',
            content: <div>main content</div>,
          },
        }}
      />,
    );

    expect(screen.getByTestId('product-shell-top-bar')).toHaveTextContent('global navigation');
    expect(screen.getByTestId('product-shell-header')).toHaveTextContent('knowledge base header');
    expect(screen.getByTestId('product-shell-navigation')).toHaveTextContent('navigation content');
    expect(screen.getByTestId('product-shell-navigator')).toHaveTextContent('navigator content');
    expect(screen.getByTestId('product-shell-main')).toHaveTextContent('main content');

    const props = productShellMock.mock.calls.at(-1)?.[0] as ProductShellProps;
    expect(props.body.kind).toBe('regions');
    if (props.body.kind !== 'regions') {
      throw new Error('Expected a regions body');
    }
    expect(props.body.navigation?.behavior).toEqual({
      collapsible: true,
      resizable: true,
      defaultWidth: 240,
      minWidth: 240,
      maxWidth: 600,
    });
    expect(props.body.navigator?.behavior).toEqual({
      collapsible: true,
      resizable: true,
      defaultWidth: 270,
      minWidth: 270,
      maxWidth: 600,
    });
    expect(props.body.navigation?.presentation.responsive).toBe('always');
    expect(props.body.navigator?.presentation.responsive).toBe('always');
    expect(props.body.navigation?.presentation.chrome).toBe('navigation');
    expect(props.body.navigator?.presentation.chrome).toBe('navigator-muted');
    const navigatorIcon = props.body.navigator?.presentation.header?.leading;
    expect(navigatorIcon).toMatchObject({
      props: {
        'aria-hidden': 'true',
        className: 'h-4 w-4 shrink-0 text-primary',
      },
    });
  });

  it('keeps loading and access states as ProductShell state bodies', () => {
    render(
      <KnowledgeBaseShellAdapter
        navigationSlot={<div>global navigation</div>}
        surface={{
          kind: 'state',
          content: <div>loading state</div>,
        }}
      />,
    );

    expect(screen.getByTestId('product-shell-state')).toHaveTextContent('loading state');
    const props = productShellMock.mock.calls.at(-1)?.[0] as ProductShellProps;
    expect(props.body).toEqual({ kind: 'state', content: expect.anything() });
  });
});
