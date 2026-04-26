import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DrawioViewer } from './DrawioViewer';

const apiGetMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/api/apiClient', () => {
  class ApiError extends Error {
    readonly status: number;
    readonly errorCode?: string;
    readonly reason?: string;

    constructor(message: string, status: number, errorCode?: string, reason?: string) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.errorCode = errorCode;
      this.reason = reason;
    }
  }

  return {
    ApiError,
    ApiClient: vi.fn().mockImplementation(() => ({
      get: apiGetMock,
      post: vi.fn(),
    })),
  };
});

describe('DrawioViewer', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
  });

  it('renders read-only XML fallback and skips iframe when Draw.io is disabled', async () => {
    const { ApiError } = await import('@/shared/api/apiClient');
    apiGetMock.mockRejectedValueOnce(
      new ApiError('Draw.io unavailable', 503, 'DRAWIO_UNAVAILABLE', 'DISABLED'),
    );

    render(
      <DrawioViewer
        content="<mxfile><diagram /></mxfile>"
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
      />,
    );

    expect(await screen.findByText('workspace.fileManagement.drawio.serviceUnavailable.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.fileManagement.drawio.serviceUnavailable.disabled')).toBeInTheDocument();
    expect(screen.getByText('<mxfile><diagram /></mxfile>')).toBeInTheDocument();
    expect(document.querySelector('iframe')).not.toBeInTheDocument();

    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(1));
  });

  it('renders unreachable fallback copy for unavailable container', async () => {
    const { ApiError } = await import('@/shared/api/apiClient');
    apiGetMock.mockRejectedValueOnce(
      new ApiError('Draw.io unavailable', 503, 'DRAWIO_UNAVAILABLE', 'UNREACHABLE'),
    );

    render(
      <DrawioViewer
        content="<mxfile><diagram /></mxfile>"
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
      />,
    );

    expect(await screen.findByText('workspace.fileManagement.drawio.serviceUnavailable.unreachable')).toBeInTheDocument();
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(1));
  });

  it('renders iframe on viewer URL success', async () => {
    apiGetMock.mockResolvedValueOnce({ url: 'about:blank' });

    render(
      <DrawioViewer
        content="<mxfile><diagram /></mxfile>"
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
      />,
    );

    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(1));
    expect(document.querySelector('iframe')).toBeInTheDocument();
  });

  it('switches to bridged edit mode instead of relying on Draw.io external edit links', async () => {
    apiGetMock
      .mockResolvedValueOnce({ url: 'about:blank?mode=view' })
      .mockResolvedValueOnce({ url: 'about:blank?mode=edit' });

    render(
      <DrawioViewer
        content="<mxfile><diagram /></mxfile>"
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
      />,
    );

    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(1));
    expect(apiGetMock).toHaveBeenLastCalledWith('/api/v1/drawio/viewer?file_path=%2Fdocs%2Fdiagram.drawio&mode=view');

    fireEvent.click(screen.getByTitle('workspace.fileManagement.drawio.edit'));

    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(2));
    expect(apiGetMock).toHaveBeenLastCalledWith('/api/v1/drawio/viewer?file_path=%2Fdocs%2Fdiagram.drawio&mode=edit');
  });

  it('does not reload the iframe when autosave updates content while editing', async () => {
    apiGetMock
      .mockResolvedValueOnce({ url: 'about:blank?mode=view' })
      .mockResolvedValueOnce({ url: 'about:blank?mode=edit' });

    const { rerender } = render(
      <DrawioViewer
        content={'<mxfile><diagram id="before" /></mxfile>'}
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
      />,
    );

    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTitle('workspace.fileManagement.drawio.edit'));
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(2));

    rerender(
      <DrawioViewer
        content={'<mxfile><diagram id="after" /></mxfile>'}
        filePath="/docs/diagram.drawio"
        runtimeBaseUrl="http://runtime.local"
      />,
    );

    await new Promise(resolve => setTimeout(resolve, 0));
    expect(apiGetMock).toHaveBeenCalledTimes(2);
  });
});
