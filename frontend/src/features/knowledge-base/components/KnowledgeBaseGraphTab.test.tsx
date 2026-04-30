import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseGraphTab } from './KnowledgeBaseGraphTab';

const {
  getGraphMock,
  apiGetMock,
  loadGraphMock,
  registerEventsMock,
  translateMock,
} = vi.hoisted(() => ({
  getGraphMock: vi.fn(),
  apiGetMock: vi.fn(),
  loadGraphMock: vi.fn(),
  registerEventsMock: vi.fn(),
  translateMock: vi.fn((key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.graph.title': '知識關聯圖',
      'knowledgeBase.graph.loading': '正在建立關聯圖...',
      'knowledgeBase.graph.loadFailed': '無法載入關聯圖',
      'knowledgeBase.graph.emptyTitle': '尚未建立 Wiki 頁面',
      'knowledgeBase.graph.emptyDescription': '執行 Wiki index 後會產生頁面與關聯。',
      'knowledgeBase.graph.searchLabel': '搜尋關聯圖節點',
      'knowledgeBase.graph.searchPlaceholder': '搜尋頁面、路徑或類型...',
      'knowledgeBase.graph.preview.emptyTitle': '頁面預覽',
      'knowledgeBase.graph.preview.emptyDescription': '尚未選擇頁面',
      'knowledgeBase.graph.preview.selectHint': '選取關聯圖節點後，可預覽 Wiki 頁面與關聯原因。',
      'knowledgeBase.graph.preview.relationships': '相關頁面',
      'knowledgeBase.graph.preview.loading': '正在載入頁面預覽...',
      'knowledgeBase.graph.legend.title': '節點類型',
      'knowledgeBase.graph.actions.zoomIn': '放大',
      'knowledgeBase.graph.actions.zoomOut': '縮小',
      'knowledgeBase.graph.actions.fit': '符合畫面',
      'knowledgeBase.graph.actions.clearSearch': '清除搜尋',
      'knowledgeBase.graph.actions.closePreview': '關閉預覽',
      'knowledgeBase.graph.types.entity': '實體',
      'knowledgeBase.graph.types.concept': '概念',
      'knowledgeBase.graph.reasons.direct_wikilink': 'Wiki 連結',
    };
    if (key === 'knowledgeBase.graph.stats.pages') return `${params?.count} 個頁面`;
    if (key === 'knowledgeBase.graph.stats.relationships') return `${params?.count} 個關聯`;
    if (key === 'knowledgeBase.graph.stats.degree') return `${params?.count} 個關聯`;
    if (key === 'knowledgeBase.graph.stats.sources') return `${params?.count} 個來源`;
    return translations[key] ?? String(params?.defaultValue ?? key);
  }),
}));

vi.mock('@react-sigma/core', () => ({
  SigmaContainer: ({ children }: { children: ReactNode }) => <div data-testid="sigma-container">{children}</div>,
  useLoadGraph: () => loadGraphMock,
  useRegisterEvents: () => registerEventsMock,
  useSigma: () => ({
    getCamera: () => ({
      animatedZoom: vi.fn(),
      animatedUnzoom: vi.fn(),
      animatedReset: vi.fn(),
    }),
    getContainer: () => ({ style: {} }),
    getGraph: () => ({
      neighbors: () => [],
      forEachNode: vi.fn(),
      forEachEdge: vi.fn(),
      setNodeAttribute: vi.fn(),
      removeNodeAttribute: vi.fn(),
      setEdgeAttribute: vi.fn(),
      removeEdgeAttribute: vi.fn(),
    }),
    refresh: vi.fn(),
  }),
}));

vi.mock('graphology-layout-forceatlas2', () => ({
  default: {
    inferSettings: vi.fn(() => ({})),
    assign: vi.fn(),
  },
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  getKnowledgeBaseGraph: getGraphMock,
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

describe('KnowledgeBaseGraphTab', () => {
  beforeEach(() => {
    getGraphMock.mockReset();
    apiGetMock.mockReset();
    loadGraphMock.mockReset();
    registerEventsMock.mockReset();
  });

  it('renders graph nodes, edges, and type legend', async () => {
    getGraphMock.mockResolvedValue({
      kbId: 'kb-1',
      generatedAt: '2026-04-29T00:00:00Z',
      nodes: [
        {
          id: 'wiki/entities/acme',
          label: 'Acme',
          type: 'entity',
          path: 'wiki/entities/acme.md',
          sources: ['raw/sources/acme.md'],
          outboundCount: 1,
          inboundCount: 0,
          degree: 1,
        },
        {
          id: 'wiki/concepts/strategy',
          label: 'Strategy',
          type: 'concept',
          path: 'wiki/concepts/strategy.md',
          sources: ['raw/sources/acme.md'],
          outboundCount: 0,
          inboundCount: 1,
          degree: 1,
        },
      ],
      edges: [
        {
          id: 'wiki/entities/acme--wiki/concepts/strategy',
          source: 'wiki/entities/acme',
          target: 'wiki/concepts/strategy',
          weight: 1.15,
          reasons: [{ type: 'direct_wikilink', weight: 1 }],
        },
      ],
    });

    render(<KnowledgeBaseGraphTab knowledgeBaseId="kb-1" />);

    expect(await screen.findByText('知識關聯圖')).toBeInTheDocument();
    expect(screen.getByText('2 個頁面')).toBeInTheDocument();
    expect(screen.getByText('1 個關聯')).toBeInTheDocument();
    expect(screen.getByText('節點類型')).toBeInTheDocument();
    expect(screen.getByText('實體')).toBeInTheDocument();
    expect(screen.getByText('概念')).toBeInTheDocument();
    expect(screen.getByTestId('sigma-container')).toBeInTheDocument();
    await waitFor(() => expect(loadGraphMock).toHaveBeenCalledTimes(1));
  });

  it('renders empty state when graph has no pages', async () => {
    getGraphMock.mockResolvedValue({
      kbId: 'kb-1',
      generatedAt: '2026-04-29T00:00:00Z',
      nodes: [],
      edges: [],
    });

    render(<KnowledgeBaseGraphTab knowledgeBaseId="kb-1" />);

    expect(await screen.findByText('尚未建立 Wiki 頁面')).toBeInTheDocument();
    expect(screen.getByText('執行 Wiki index 後會產生頁面與關聯。')).toBeInTheDocument();
  });

  it('highlights matching nodes from search input', async () => {
    getGraphMock.mockResolvedValue({
      kbId: 'kb-1',
      generatedAt: '2026-04-29T00:00:00Z',
      nodes: [
        {
          id: 'wiki/entities/acme',
          label: 'Acme',
          type: 'entity',
          path: 'wiki/entities/acme.md',
          sources: [],
          outboundCount: 0,
          inboundCount: 0,
          degree: 0,
        },
      ],
      edges: [],
    });

    render(<KnowledgeBaseGraphTab knowledgeBaseId="kb-1" />);

    const input = await screen.findByLabelText('搜尋關聯圖節點');
    fireEvent.change(input, { target: { value: 'acme' } });

    expect(input).toHaveValue('acme');
    expect(screen.getByLabelText('清除搜尋')).toBeInTheDocument();
  });

  it('opens a wiki page preview when a graph node is selected', async () => {
    getGraphMock.mockResolvedValue({
      kbId: 'kb-1',
      generatedAt: '2026-04-29T00:00:00Z',
      nodes: [
        {
          id: 'wiki/entities/acme',
          label: 'Acme',
          type: 'entity',
          path: 'wiki/entities/acme.md',
          sources: ['raw/sources/acme.md'],
          outboundCount: 1,
          inboundCount: 0,
          degree: 1,
        },
        {
          id: 'wiki/concepts/strategy',
          label: 'Strategy',
          type: 'concept',
          path: 'wiki/concepts/strategy.md',
          sources: [],
          outboundCount: 0,
          inboundCount: 1,
          degree: 1,
        },
      ],
      edges: [
        {
          id: 'wiki/entities/acme--wiki/concepts/strategy',
          source: 'wiki/entities/acme',
          target: 'wiki/concepts/strategy',
          weight: 1,
          reasons: [{ type: 'direct_wikilink', weight: 1 }],
        },
      ],
    });
    apiGetMock.mockResolvedValue({ content: '# Acme\n\nPreview content.' });

    render(<KnowledgeBaseGraphTab knowledgeBaseId="kb-1" />);

    await screen.findByText('知識關聯圖');
    const events = registerEventsMock.mock.calls[0]?.[0];
    expect(() => events.enterNode({ node: 'wiki/entities/acme' })).not.toThrow();
    expect(() => events.leaveNode()).not.toThrow();
    await act(async () => {
      await events.clickNode({ node: 'wiki/entities/acme' });
    });

    await waitFor(() => expect(screen.getAllByText('Acme').length).toBeGreaterThan(0));
    expect(apiGetMock).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/content?path=%2Fwiki%2Fentities%2Facme.md');
    expect(await screen.findByText('Preview content.')).toBeInTheDocument();
    expect(screen.getByText('相關頁面')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
  });
});
