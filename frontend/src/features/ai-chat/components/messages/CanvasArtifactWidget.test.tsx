// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CanvasArtifactWidget } from './CanvasArtifactWidget';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const { openCanvasMock, integration } = vi.hoisted(() => {
  const openCanvas = vi.fn();
  return {
    openCanvasMock: openCanvas,
    integration: { openCanvas: openCanvas as (() => void) | null },
  };
});

vi.mock('../../contexts/AiChatIntegrationContext', () => ({
  useAiChatIntegration: () => integration,
}));

const renderWidget = (props: Parameters<typeof CanvasArtifactWidget>[0]) =>
  render(<CanvasArtifactWidget {...props} />);

describe('CanvasArtifactWidget', () => {
  beforeEach(() => {
    openCanvasMock.mockClear();
    integration.openCanvas = openCanvasMock;
  });

  it('renders safely without a Canvas integration and disables the open action', () => {
    integration.openCanvas = null;

    const { container } = renderWidget({
      id: '7',
      name: 'mcp__aileron__show_canvas_artifact',
      parameters: { title: 'Scheduled landing page', route: '/landing' },
      status: 'completed',
    });

    const button = within(container).getByRole('button', { name: /Scheduled landing page/ });
    expect(button).toBeDisabled();
    expect(within(container).queryByText('aiChat.canvasArtifact.open')).not.toBeInTheDocument();
  });

  it('renders the model-provided title verbatim as a clickable button', () => {
    const { container } = renderWidget({
      id: '7',
      name: 'mcp__aileron__show_canvas_artifact',
      parameters: { title: 'Landing page', route: '/landing' },
      status: 'completed',
    });
    const button = within(container).getByRole('button', { name: /Landing page/ });
    expect(button).toBeInTheDocument();
    expect(button).toBeEnabled();
  });

  it('falls back to the default title key when title is missing', () => {
    const { container } = renderWidget({
      id: '7',
      name: 'mcp__aileron__show_canvas_artifact',
      parameters: {},
      status: 'completed',
    });
    expect(within(container).getByText('aiChat.canvasArtifact.defaultTitle')).toBeInTheDocument();
  });

  it('visually distinguishes pending artifacts and disables the button', () => {
    const { container } = renderWidget({
      id: '7',
      name: 'mcp__aileron__show_canvas_artifact',
      parameters: { title: 'Landing page' },
      status: 'pending',
    });

    const widget = within(container).getByText('Landing page').closest('[data-status]');
    expect(widget).toHaveAttribute('data-status', 'pending');
    expect(widget).toHaveClass('opacity-70');
    expect(widget?.querySelector('.animate-spin')).not.toBeNull();
    expect(within(container).getByRole('button', { name: /Landing page/ })).toBeDisabled();
  });

  it('delegates opening the Canvas artifact to the integration callback', () => {
    const { container } = renderWidget({
      id: '7',
      name: 'mcp__aileron__show_canvas_artifact',
      parameters: { title: 'Landing page', route: '/landing' },
      status: 'completed',
    });

    fireEvent.click(within(container).getByRole('button', { name: /Landing page/ }));

    expect(openCanvasMock).toHaveBeenCalledTimes(1);
  });
});
