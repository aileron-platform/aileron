import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';
import { MermaidViewer } from './MermaidViewer';
import { ImageViewer } from './ImageViewer';
import { DrawioViewer } from './DrawioViewer';

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: '<svg />' })),
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.local',
    },
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    getBlob: vi.fn(async () => new Blob(['image'], { type: 'image/png' })),
    get: vi.fn(async () => ({ url: 'about:blank' })),
  })),
}));

describe('specialized viewer focus toolbars', () => {
  it('shows Mermaid focus tools without a duplicate expand control', () => {
    render(
      <MermaidViewer
        content="graph TD; A-->B;"
        fileName="diagram.mmd"
        isFocusMode
        onExitFocusMode={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'workspace.fileManagement.focus.exit' })).toBeInTheDocument();
    expect(screen.getByTitle('workspace.fileManagement.mermaid.zoomIn')).toBeInTheDocument();
    expect(screen.queryByTitle('workspace.fileManagement.mermaid.expand')).not.toBeInTheDocument();
  });

  it('shows image focus tools without a duplicate expand control', () => {
    render(
      <ImageViewer
        filePath="/assets/logo.png"
        fileName="logo.png"
        isFocusMode
        onExitFocusMode={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'workspace.fileManagement.focus.exit' })).toBeInTheDocument();
    expect(screen.getByTitle('workspace.fileManagement.image.rotate')).toBeInTheDocument();
    expect(screen.queryByTitle('workspace.fileManagement.image.expand')).not.toBeInTheDocument();
  });

  it('shows Draw.io focus tools without a duplicate expand control', () => {
    render(
      <DrawioViewer
        content="<mxfile />"
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
        isFocusMode
        onExitFocusMode={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'workspace.fileManagement.focus.exit' })).toBeInTheDocument();
    expect(screen.getByTitle('workspace.fileManagement.drawio.download')).toBeInTheDocument();
    expect(screen.queryByTitle('workspace.fileManagement.drawio.expand')).not.toBeInTheDocument();
  });
});
