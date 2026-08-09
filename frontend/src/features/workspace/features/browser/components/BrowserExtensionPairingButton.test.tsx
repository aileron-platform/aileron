import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { BrowserExtensionPairingButton } from './BrowserExtensionPairingButton';

const {
  createPairingAssertionMock,
  deliverPairingMock,
  resolveExtensionIdMock,
  toastMock,
} = vi.hoisted(() => ({
  createPairingAssertionMock: vi.fn(),
  deliverPairingMock: vi.fn(),
  resolveExtensionIdMock: vi.fn(),
  toastMock: vi.fn(),
}));

vi.mock('../../../api/workspaceBrowserExtensionApi', () => ({
  workspaceBrowserExtensionApi: {
    createPairingAssertion: createPairingAssertionMock,
  },
}));

vi.mock('../../../config/browserExtensionConfig', () => ({
  resolveBrowserExtensionId: resolveExtensionIdMock,
}));

vi.mock('../../../services/browserExtensionPairingTransport', () => ({
  deliverBrowserExtensionPairing: deliverPairingMock,
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const extensionId = 'abcdefghijklmnopabcdefghijklmnop';
const pairing = {
  assertion: 'header.payload.signature',
  runtimeInstanceId: 'runtime-instance-123',
};

describe('BrowserExtensionPairingButton', () => {
  beforeEach(() => {
    createPairingAssertionMock.mockReset();
    deliverPairingMock.mockReset();
    resolveExtensionIdMock.mockReset();
    toastMock.mockReset();
    resolveExtensionIdMock.mockReturnValue(extensionId);
    createPairingAssertionMock.mockResolvedValue(pairing);
    deliverPairingMock.mockResolvedValue(undefined);
  });

  it('uses one explicit click to fetch and deliver a short-lived assertion', async () => {
    const user = userEvent.setup();
    render(<BrowserExtensionPairingButton workspaceId="workspace-one" />);

    await user.click(
      screen.getByRole('button', {
        name: 'workspace.browser.extensionPairing.action',
      })
    );

    await waitFor(() => {
      expect(createPairingAssertionMock).toHaveBeenCalledWith('workspace-one');
      expect(deliverPairingMock).toHaveBeenCalledWith(extensionId, pairing);
    });
    expect(toastMock).toHaveBeenCalledWith({
      title: 'workspace.browser.extensionPairing.success.title',
      description:
        'workspace.browser.extensionPairing.success.description',
    });
    expect(document.body.textContent).not.toContain(pairing.assertion);
  });

  it('is absent when the deployment has no valid extension identifier', () => {
    resolveExtensionIdMock.mockReturnValue(null);

    const { container } = render(
      <BrowserExtensionPairingButton workspaceId="workspace-one" />
    );

    expect(container).toBeEmptyDOMElement();
    expect(createPairingAssertionMock).not.toHaveBeenCalled();
  });

  it('shows only a localized generic failure when delivery is rejected', async () => {
    const user = userEvent.setup();
    deliverPairingMock.mockRejectedValue(new Error(pairing.assertion));
    render(<BrowserExtensionPairingButton workspaceId="workspace-one" />);

    await user.click(
      screen.getByRole('button', {
        name: 'workspace.browser.extensionPairing.action',
      })
    );

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({
        title: 'workspace.browser.extensionPairing.error.title',
        description:
          'workspace.browser.extensionPairing.error.description',
        variant: 'destructive',
      });
    });
    expect(document.body.textContent).not.toContain(pairing.assertion);
  });
});
