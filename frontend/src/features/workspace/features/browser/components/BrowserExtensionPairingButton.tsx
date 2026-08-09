import { useState } from 'react';
import { Link, Loader2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { workspaceBrowserExtensionApi } from '../../../api/workspaceBrowserExtensionApi';
import { resolveBrowserExtensionId } from '../../../config/browserExtensionConfig';
import { deliverBrowserExtensionPairing } from '../../../services/browserExtensionPairingTransport';

interface BrowserExtensionPairingButtonProps {
  workspaceId: string | null | undefined;
  disabled?: boolean;
}

export function BrowserExtensionPairingButton({
  workspaceId,
  disabled = false,
}: BrowserExtensionPairingButtonProps) {
  const { t } = useI18n();
  const { toast } = useToast();
  const [isPairing, setIsPairing] = useState(false);
  const extensionId = resolveBrowserExtensionId();

  if (extensionId === null) {
    return null;
  }

  const handlePairing = async () => {
    if (!workspaceId || isPairing) {
      return;
    }
    setIsPairing(true);
    try {
      const pairing = await workspaceBrowserExtensionApi.createPairingAssertion(
        workspaceId
      );
      await deliverBrowserExtensionPairing(extensionId, pairing);
      toast({
        title: t('workspace.browser.extensionPairing.success.title'),
        description: t(
          'workspace.browser.extensionPairing.success.description'
        ),
      });
    } catch {
      toast({
        title: t('workspace.browser.extensionPairing.error.title'),
        description: t(
          'workspace.browser.extensionPairing.error.description'
        ),
        variant: 'destructive',
      });
    } finally {
      setIsPairing(false);
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 px-2 text-xs"
      onClick={handlePairing}
      disabled={disabled || !workspaceId || isPairing}
      title={t('workspace.browser.extensionPairing.action')}
    >
      {isPairing ? (
        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
      ) : (
        <Link className="mr-1.5 h-3.5 w-3.5" />
      )}
      {isPairing
        ? t('workspace.browser.extensionPairing.connecting')
        : t('workspace.browser.extensionPairing.action')}
    </Button>
  );
}
