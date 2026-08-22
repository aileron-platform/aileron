import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProductShell } from './ProductShell';
import type {
  ProductShellBody,
  ProductShellColumnRegion,
  ProductShellCompanionRegion,
  ProductShellPreferencesAdapter,
} from './productShellTypes';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const makeColumn = (
  name: string,
  overrides: Partial<ProductShellColumnRegion> = {},
): ProductShellColumnRegion => ({
  content: ({ collapsed }) => (
    <div data-testid={`${name}-content`} data-collapsed={String(collapsed)}>{name}</div>
  ),
  behavior: {
    collapsible: true,
    resizable: true,
    defaultWidth: 240,
    minWidth: 160,
    maxWidth: 560,
  },
  presentation: {
    accessibleLabel: `${name}-label`,
    responsive: 'always',
  },
  ...overrides,
});

const makeCompanion = (
  overrides: Partial<ProductShellCompanionRegion> = {},
): ProductShellCompanionRegion => ({
  content: ({ placement, collapsed, fullscreen }) => (
    <div
      data-testid="companion-content"
      data-placement={placement}
      data-collapsed={String(collapsed)}
      data-fullscreen={String(fullscreen)}
    >
      companion
    </div>
  ),
  placement: 'side',
  side: {
    collapsible: true,
    resizable: true,
    defaultWidth: 280,
    minWidth: 200,
    maxWidth: 640,
  },
  bottom: {
    defaultHeight: 240,
    minHeight: 120,
    maxHeight: 500,
    mainMinHeight: 320,
  },
  presentation: {
    accessibleLabel: 'companion-label',
    rail: 'standard',
    collapseLabel: 'collapse companion',
    expandLabel: 'expand companion',
    resizeLabel: 'resize companion',
    collapsedContent: <div data-testid="companion-collapsed">collapsed companion</div>,
  },
  ...overrides,
});

const makeBody = (overrides: Partial<Extract<ProductShellBody, { kind: 'regions' }>> = {}): Extract<ProductShellBody, { kind: 'regions' }> => ({
  kind: 'regions',
  navigation: makeColumn('navigation'),
  navigator: makeColumn('navigator'),
  main: { accessibleLabel: 'main-label', content: <div data-testid="main-content">main</div> },
  companion: makeCompanion(),
  ...overrides,
});

const makeAdapter = (initial: ReturnType<NonNullable<ProductShellPreferencesAdapter['load']>> = null): ProductShellPreferencesAdapter & { saves: ReturnType<typeof vi.fn> } => {
  const saves = vi.fn();
  return {
    identity: 'entity-1',
    load: vi.fn(() => initial),
    save: saves,
    saves,
  };
};

afterEach(() => {
  vi.useRealTimers();
});

describe('ProductShell', () => {
  it('renders semantic regions in order and omits absent regions completely', () => {
    render(
      <ProductShell
        topBar={<div data-testid="top-bar">top</div>}
        header={<div data-testid="shell-header">header</div>}
        body={makeBody({ navigator: undefined, companion: undefined })}
      />,
    );

    fireEvent(window, new Event('resize'));

    const shell = screen.getByTestId('product-shell');
    const regionNames = [...shell.querySelectorAll('[data-shell-region]')]
      .map((element) => element.getAttribute('data-shell-region'));
    expect(regionNames).toEqual(['navigation', 'main']);
    expect(screen.getByTestId('top-bar')).toBeInTheDocument();
    expect(screen.getByTestId('shell-header')).toBeInTheDocument();
    expect(screen.queryByTestId('navigator-content')).not.toBeInTheDocument();
    expect(screen.queryByTestId('companion-content')).not.toBeInTheDocument();
    expect(screen.queryAllByRole('separator')).toHaveLength(1);
  });

  it('provides a flex height context for main region content', () => {
    render(
      <ProductShell
        body={makeBody({ navigation: undefined, navigator: undefined, companion: undefined })}
      />,
    );

    expect(screen.getByTestId('main-content').parentElement).toHaveClass(
      'flex',
      'min-h-0',
      'flex-1',
      'flex-col',
      'overflow-hidden',
    );
  });

  it('owns one background surface across every shell column', () => {
    render(<ProductShell body={makeBody()} />);

    const shell = screen.getByTestId('product-shell');
    const shellBody = shell.querySelector('[data-shell-body]');
    expect(shellBody).toHaveClass('bg-background');

    shell.querySelectorAll('[data-shell-region]').forEach((region) => {
      expect(region).toHaveClass('bg-background');
    });

    expect(screen.getByTestId('navigation-content').parentElement).toHaveClass('bg-background');
    expect(screen.getByTestId('navigator-content').parentElement).toHaveClass('bg-background');
    expect(screen.getByTestId('companion-content').parentElement).toHaveClass('bg-background');
    expect(shell.querySelector('[class~="bg-muted/20"]')).not.toBeInTheDocument();
  });

  it('renders state bodies without region DOM or resize handles', () => {
    const adapter = makeAdapter({ navigation: { collapsed: false, width: 480 } });
    render(
      <ProductShell
        topBar={<div data-testid="top-bar">top</div>}
        header={<div data-testid="shell-header">header</div>}
        preferences={adapter}
        body={{ kind: 'state', content: <div data-testid="state-content">loading</div> }}
      />,
    );

    expect(screen.getByTestId('state-content')).toBeInTheDocument();
    expect(screen.getByTestId('state-content').closest('[data-shell-state]')).toHaveClass(
      'flex-col',
      'bg-background',
    );
    expect(screen.queryByTestId('navigation-content')).not.toBeInTheDocument();
    expect(screen.queryByRole('separator')).not.toBeInTheDocument();
    expect(adapter.load).toHaveBeenCalledTimes(1);
  });

  it('does not attach shell resize listeners or retain pending saves for state bodies', () => {
    vi.useFakeTimers();
    const adapter = makeAdapter(null);
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    const { rerender } = render(<ProductShell body={makeBody()} preferences={adapter} />);
    fireEvent.click(within(screen.getByRole('complementary', { name: 'navigation-label' }))
      .getByRole('button', { name: 'shared.shell.collapseSidebar' }));
    const resizeListenerCount = addEventListenerSpy.mock.calls.filter(([type]) => type === 'resize').length;
    rerender(
      <ProductShell
        body={{ kind: 'state', content: <div data-testid="state-content">loading</div> }}
        preferences={adapter}
      />,
    );
    vi.advanceTimersByTime(500);
    expect(adapter.saves).not.toHaveBeenCalled();
    expect(addEventListenerSpy.mock.calls.filter(([type]) => type === 'resize')).toHaveLength(resizeListenerCount);
    addEventListenerSpy.mockRestore();
  });

  it('applies the shared column surface, header slots and read-only collapse state', () => {
    render(
      <ProductShell
        body={makeBody({
          navigation: makeColumn('navigation', {
            presentation: {
              accessibleLabel: 'navigation label',
              responsive: 'always',
              header: {
                leading: <span data-testid="header-leading">leading</span>,
                title: <span data-testid="header-title">title</span>,
                info: <span data-testid="header-info">info</span>,
                actions: <button type="button">header action</button>,
              },
            },
          }),
        })}
      />,
    );

    const navigation = screen.getByRole('complementary', { name: 'navigation label' });
    expect(navigation).toHaveAttribute('data-shell-region', 'navigation');
    expect(screen.getByTestId('header-leading')).toBeInTheDocument();
    expect(screen.getByTestId('header-title')).toBeInTheDocument();
    expect(screen.getByTestId('header-title').parentElement).toHaveClass(
      'text-sm',
      'font-medium',
      'text-foreground',
    );
    expect(screen.getByTestId('header-info')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'header action' })).toBeInTheDocument();

    fireEvent.click(within(navigation).getByRole('button', { name: 'shared.shell.collapseSidebar' }));
    expect(screen.getByTestId('navigation-content')).toHaveAttribute('data-collapsed', 'true');
    expect(screen.queryByTestId('header-leading')).not.toBeInTheDocument();
    expect(screen.queryByTestId('header-title')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.shell.expandSidebar' })).toBeInTheDocument();
  });

  it('keeps a collapsed navigator icon in the content row below the expand control', () => {
    render(
      <ProductShell
        body={makeBody({
          navigator: makeColumn('navigator', {
            presentation: {
              accessibleLabel: 'navigator label',
              responsive: 'always',
              header: {
                leading: <span data-testid="navigator-header-icon">icon</span>,
                title: 'Navigator',
              },
            },
          }),
        })}
      />,
    );

    const navigator = screen.getByRole('complementary', { name: 'navigator label' });
    fireEvent.click(within(navigator).getByRole('button', { name: 'shared.shell.collapseSidebar' }));

    expect(screen.queryByTestId('navigator-header-icon')).toBeInTheDocument();
    expect(screen.getByTestId('navigator-header-icon').parentElement).toHaveClass('pt-3');
    const collapsedHeader = navigator.querySelector('.h-10');
    expect(collapsedHeader).not.toBeNull();
    expect(collapsedHeader).not.toContainElement(screen.getByTestId('navigator-header-icon'));
    expect(within(navigator).getByRole('button', { name: 'shared.shell.expandSidebar' })).toBeInTheDocument();
  });

  it('supports main-expanded and companion-fullscreen display callbacks and Escape', () => {
    const onMainExit = vi.fn();
    const { rerender } = render(
      <ProductShell body={makeBody()} display={{ mode: 'main-expanded', onExit: onMainExit }} />,
    );
    expect(screen.queryByTestId('top-bar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('navigation-content')).not.toBeInTheDocument();
    expect(screen.queryByTestId('navigator-content')).not.toBeInTheDocument();
    expect(screen.getByTestId('main-content')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onMainExit).toHaveBeenCalledTimes(1);

    const onCompanionExit = vi.fn();
    rerender(
      <ProductShell body={makeBody()} display={{ mode: 'companion-fullscreen', onExit: onCompanionExit }} />,
    );
    expect(screen.queryByTestId('main-content')).not.toBeInTheDocument();
    expect(screen.getByTestId('companion-content')).toHaveAttribute('data-fullscreen', 'true');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCompanionExit).toHaveBeenCalledTimes(1);
  });

  it('renders side and bottom companion states with the shared resize controls', () => {
    const { rerender } = render(<ProductShell body={makeBody()} />);
    expect(screen.getByRole('region', { name: 'companion-label' })).toHaveStyle({ width: '224px' });
    expect(screen.getByTestId('companion-content')).toHaveAttribute('data-placement', 'side');
    expect(screen.getAllByRole('separator')).toHaveLength(3);

    fireEvent.click(screen.getByRole('button', { name: 'collapse companion' }));
    expect(screen.getByTestId('companion-collapsed')).toBeInTheDocument();
    expect(screen.queryByTestId('companion-content')).not.toBeInTheDocument();

    rerender(<ProductShell body={makeBody({ companion: makeCompanion({ placement: 'bottom' }) })} />);
    expect(screen.getByRole('region', { name: 'companion-label' })).toHaveStyle({ height: '240px' });
    expect(screen.getByTestId('companion-content')).toHaveAttribute('data-placement', 'bottom');
    expect(screen.getByTestId('companion-content')).toHaveAttribute('data-collapsed', 'false');
  });

  it('temporarily yields the side companion without changing navigation or saved preferences', () => {
    vi.useFakeTimers();
    const originalInnerWidth = window.innerWidth;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
    const adapter = makeAdapter(null);
    render(
      <ProductShell
        body={makeBody({
          navigation: makeColumn('navigation', {
            behavior: {
              collapsible: true,
              resizable: true,
              defaultWidth: 240,
              minWidth: 240,
              maxWidth: 500,
            },
          }),
          navigator: makeColumn('navigator', {
            behavior: {
              collapsible: true,
              resizable: true,
              defaultWidth: 270,
              minWidth: 270,
              maxWidth: 600,
            },
          }),
          companion: makeCompanion({
            side: {
              collapsible: true,
              resizable: true,
              defaultWidth: 408,
              minWidth: 408,
              maxWidth: 640,
            },
            presentation: {
              accessibleLabel: 'companion-label',
              rail: 'compact',
              collapseLabel: 'collapse companion',
              expandLabel: 'expand companion',
              resizeLabel: 'resize companion',
              collapsedContent: <div data-testid="companion-collapsed">collapsed companion</div>,
            },
          }),
        })}
        preferences={adapter}
      />,
    );

    expect(screen.getByRole('complementary', { name: 'navigation-label' })).toHaveStyle({ width: '240px' });
    expect(screen.getByRole('complementary', { name: 'navigator-label' })).toHaveStyle({ width: '270px' });
    expect(screen.getByRole('region', { name: 'companion-label' })).toHaveStyle({ width: '48px' });
    expect(screen.getByTestId('companion-collapsed')).toBeInTheDocument();
    vi.advanceTimersByTime(500);
    expect(adapter.saves).not.toHaveBeenCalled();

    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 });
    fireEvent(window, new Event('resize'));

    expect(screen.getByRole('region', { name: 'companion-label' })).toHaveStyle({ width: '408px' });
    expect(screen.getByTestId('companion-content')).toHaveAttribute('data-collapsed', 'false');
    vi.advanceTimersByTime(500);
    expect(adapter.saves).not.toHaveBeenCalled();
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalInnerWidth });
  });

  it('does not allocate a bottom companion header when the presentation omits it', () => {
    render(
      <ProductShell
        body={makeBody({
          companion: makeCompanion({ placement: 'bottom' }),
        })}
      />,
    );

    const companion = screen.getByRole('region', { name: 'companion-label' });
    expect(screen.getByTestId('companion-content')).toBeInTheDocument();
    expect(within(companion).queryByTestId('shell-companion-header')).not.toBeInTheDocument();
    expect(within(companion).queryByRole('separator', { name: 'resize companion' })).toBeInTheDocument();
  });

  it('keeps responsive overflow ownership in ProductShell regions', () => {
    render(
      <ProductShell
        body={makeBody({
          navigator: makeColumn('navigator', {
            presentation: {
              accessibleLabel: 'navigator-label',
              responsive: 'desktop-up',
            },
          }),
        })}
      />,
    );

    expect(screen.getByRole('complementary', { name: 'navigator-label' })).toHaveClass(
      'max-[1023px]:hidden',
    );
  });

  it('reveals a side companion only for a subsequent request on the same identity', () => {
    const first = makeCompanion({ revealRequestId: 4 });
    const adapter = makeAdapter({ companion: { collapsed: true, width: 300, height: 240, placement: 'side' } });
    const { rerender } = render(
      <ProductShell
        body={makeBody({ companion: first })}
        preferences={adapter}
      />,
    );
    expect(screen.getByTestId('companion-collapsed')).toBeInTheDocument();

    rerender(
      <ProductShell
        body={makeBody({ companion: { ...first, revealRequestId: 5 } })}
        preferences={adapter}
      />,
    );
    expect(screen.getByTestId('companion-content')).toBeInTheDocument();
  });

  it('debounces interactive preference saves and does not save display-only changes', () => {
    vi.useFakeTimers();
    const adapter = makeAdapter(null);
    const { rerender } = render(<ProductShell body={makeBody()} preferences={adapter} />);
    expect(adapter.load).toHaveBeenCalledTimes(1);
    expect(adapter.saves).not.toHaveBeenCalled();

    fireEvent.click(within(screen.getByRole('complementary', { name: 'navigation-label' }))
      .getByRole('button', { name: 'shared.shell.collapseSidebar' }));
    vi.advanceTimersByTime(499);
    expect(adapter.saves).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(adapter.saves).toHaveBeenCalledTimes(1);

    const saveCount = adapter.saves.mock.calls.length;
    rerender(<ProductShell body={makeBody()} preferences={adapter} display={{ mode: 'main-expanded', onExit: vi.fn() }} />);
    vi.advanceTimersByTime(500);
    expect(adapter.saves).toHaveBeenCalledTimes(saveCount);
  });
});
