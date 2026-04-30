import React, { useState, useEffect } from 'react';
import { Key, RefreshCw, Save } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  getSSHKeys,
  generateSSHKeys,
  updateSSHKeys,
  type SSHKeys,
} from '@/features/template-management/api/templateSshApi';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SSHKeysTab');

interface SSHKeysTabProps {
  value: SSHKeys | null;
  onChange: (keys: SSHKeys) => void;
}

export const SSHKeysTab: React.FC<SSHKeysTabProps> = ({ value, onChange }) => {
  const { toast } = useToast();
  const { t } = useI18n();

  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showPrivateKey, setShowPrivateKey] = useState(false);
  const [sshKeys, setSshKeys] = useState<SSHKeys | null>(value);
  const [editedKeys, setEditedKeys] = useState<SSHKeys | null>(value);
  const [hasChanges, setHasChanges] = useState(false);

  // 同步外部 value 到內部狀態
  useEffect(() => {
    setSshKeys(value);
    setEditedKeys(value);
    setHasChanges(false);
  }, [value]);

  // 載入 SSH Keys
  const loadSSHKeys = async () => {
    setIsLoading(true);
    try {
      const response = await getSSHKeys();
      if (response.success && response.data) {
        const keys = response.data;
        setSshKeys(keys);
        onChange(keys);
      }
    } catch (error) {
      logger.error('載入 SSH Keys 失敗', { error });
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.toasts.loadFailed.title'),
        description: t('template.center.settingsDialog.git.sshKeys.toasts.loadFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSSHKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 產生新的 SSH Key Pair
  const handleGenerateSSHKey = async () => {
    setIsGenerating(true);
    try {
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.toasts.generating.title'),
        description: t('template.center.settingsDialog.git.sshKeys.toasts.generating.description'),
      });

      const response = await generateSSHKeys();

      if (response.success && response.data) {
        // 更新本地狀態和通知父組件
        const keys = {
          publicKey: response.data.publicKey,
          privateKey: response.data.privateKey,
          fingerprint: response.data.fingerprint,
          lastRotatedAt: response.data.generatedAt,
        };
        setSshKeys(keys);
        setEditedKeys(keys);
        setHasChanges(false);
        onChange(keys);

        toast({
          title: t('template.center.settingsDialog.git.sshKeys.toasts.generateSuccess.title'),
          description: t('template.center.settingsDialog.git.sshKeys.toasts.generateSuccess.description'),
        });
      } else {
        toast({
          title: t('template.center.settingsDialog.git.sshKeys.toasts.generateFailed.title'),
          description: response.error || t('template.center.settingsDialog.git.sshKeys.toasts.generateFailed.description'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('產生 SSH Key 失敗', { error });
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.toasts.generateFailed.title'),
        description: error instanceof Error ? error.message : t('template.center.settingsDialog.git.sshKeys.toasts.generateFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsGenerating(false);
    }
  };

  // 保存 SSH Keys
  const handleSaveSSHKeys = async () => {
    if (!editedKeys?.privateKey || !editedKeys?.publicKey) {
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.toasts.saveFailed.title'),
        description: t('template.center.settingsDialog.git.sshKeys.toasts.saveFailed.description'),
        variant: 'destructive',
      });
      return;
    }

    setIsSaving(true);
    try {
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.actions.saving'),
        description: t('template.center.settingsDialog.git.sshKeys.toasts.generating.description'),
      });

      const response = await updateSSHKeys(editedKeys.privateKey, editedKeys.publicKey);

      if (response.success && response.data) {
        const keys = {
          publicKey: response.data.publicKey,
          privateKey: response.data.privateKey,
          fingerprint: response.data.fingerprint,
          lastRotatedAt: response.data.updatedAt || response.data.generatedAt,
        };
        setSshKeys(keys);
        setEditedKeys(keys);
        setHasChanges(false);
        onChange(keys);

        toast({
          title: t('template.center.settingsDialog.git.sshKeys.toasts.saveSuccess.title'),
          description: t('template.center.settingsDialog.git.sshKeys.toasts.saveSuccess.description'),
        });
      } else {
        toast({
          title: t('template.center.settingsDialog.git.sshKeys.toasts.saveFailed.title'),
          description: response.error || t('template.center.settingsDialog.git.sshKeys.toasts.saveFailed.description'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('保存 SSH Keys 失敗', { error });
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.toasts.saveFailed.title'),
        description: error instanceof Error ? error.message : t('template.center.settingsDialog.git.sshKeys.toasts.saveFailed.description'),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  // 處理私鑰變更
  const handlePrivateKeyChange = (value: string) => {
    setEditedKeys((prev) => ({
      ...prev,
      privateKey: value,
      publicKey: prev?.publicKey || null,
      fingerprint: prev?.fingerprint || null,
      lastRotatedAt: prev?.lastRotatedAt || null,
    }));
    setHasChanges(true);
  };

  // 處理公鑰變更
  const handlePublicKeyChange = (value: string) => {
    setEditedKeys((prev) => ({
      ...prev,
      privateKey: prev?.privateKey || null,
      publicKey: value,
      fingerprint: prev?.fingerprint || null,
      lastRotatedAt: prev?.lastRotatedAt || null,
    }));
    setHasChanges(true);
  };

  // 複製到剪貼簿
  const handleCopyToClipboard = (text: string) => {
    try {
      navigator.clipboard?.writeText(text);
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.copied'),
        description: t('template.center.settingsDialog.git.sshKeys.copiedDescription'),
      });
    } catch (err) {
      logger.error('複製內容到剪貼簿時發生錯誤', { error: err });
      toast({
        title: t('template.center.settingsDialog.git.sshKeys.copyFailed'),
        description: t('template.center.settingsDialog.git.sshKeys.copyFailedDescription'),
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-2 text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>{t('template.center.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            {t('template.center.settingsDialog.git.sshKeys.title')}
          </CardTitle>
          <CardDescription>
            {t('template.center.settingsDialog.git.sshKeys.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 私鑰 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="privateKey">{t('template.center.settingsDialog.git.sshKeys.privateKeyLabel')}</Label>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowPrivateKey(!showPrivateKey)}
                >
                  {showPrivateKey ? t('template.center.settingsDialog.git.sshKeys.hidePrivateKey') : t('template.center.settingsDialog.git.sshKeys.showPrivateKey')}
                </Button>
                {sshKeys?.privateKey && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCopyToClipboard(sshKeys.privateKey!)}
                  >
                    {t('template.center.settingsDialog.git.sshKeys.copy')}
                  </Button>
                )}
              </div>
            </div>
            <Textarea
              id="privateKey"
              placeholder={t('template.center.settingsDialog.git.sshKeys.notGenerated')}
              value={
                showPrivateKey
                  ? editedKeys?.privateKey || ''
                  : editedKeys?.privateKey
                  ? '••••••••••••'
                  : ''
              }
              onChange={(e) => handlePrivateKeyChange(e.target.value)}
              className="font-mono text-sm"
              rows={8}
              disabled={!showPrivateKey}
            />
            {sshKeys?.privateKey && (
              <p className="text-xs text-muted-foreground">
                {t('template.center.settingsDialog.git.sshKeys.keepPrivateKeySafe')}
              </p>
            )}
          </div>

          {/* 公鑰 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="publicKey">{t('template.center.settingsDialog.git.sshKeys.publicKeyLabel')}</Label>
              {sshKeys?.publicKey && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopyToClipboard(sshKeys.publicKey!)}
                >
                  {t('template.center.settingsDialog.git.sshKeys.copy')}
                </Button>
              )}
            </div>
            <Textarea
              id="publicKey"
              placeholder={t('template.center.settingsDialog.git.sshKeys.notGenerated')}
              value={editedKeys?.publicKey || ''}
              onChange={(e) => handlePublicKeyChange(e.target.value)}
              className="font-mono text-sm"
              rows={4}
            />
            {sshKeys?.publicKey && (
              <p className="text-xs text-muted-foreground">
                {t('template.center.settingsDialog.git.sshKeys.addPublicKeyToGit')}
              </p>
            )}
          </div>

          {/* Fingerprint */}
          {sshKeys?.fingerprint && (
            <div className="space-y-2">
              <Label>{t('template.center.settingsDialog.git.sshKeys.fingerprintLabel')}</Label>
              <div className="rounded-md bg-muted p-3">
                <code className="text-sm">{sshKeys.fingerprint}</code>
              </div>
            </div>
          )}

          {/* 最後產生時間 */}
          {sshKeys?.lastRotatedAt && (
            <div className="space-y-2">
              <Label>{t('template.center.settingsDialog.git.sshKeys.lastRotatedLabel')}</Label>
              <div className="text-sm text-muted-foreground">
                {new Date(sshKeys.lastRotatedAt).toLocaleString('zh-TW', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </div>
            </div>
          )}

          {/* 操作按鈕 */}
          <div className="pt-4 flex gap-3">
            {hasChanges && (
              <Button
                onClick={handleSaveSSHKeys}
                disabled={isSaving || isGenerating}
                variant="default"
              >
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? t('template.center.settingsDialog.git.sshKeys.actions.saving') : t('template.center.settingsDialog.git.sshKeys.actions.save')}
              </Button>
            )}
            <Button
              onClick={handleGenerateSSHKey}
              disabled={isGenerating || isSaving}
              variant={sshKeys?.publicKey ? 'outline' : 'default'}
            >
              <Key className="h-4 w-4 mr-2" />
              {isGenerating
                ? t('template.center.settingsDialog.git.sshKeys.actions.generating')
                : sshKeys?.publicKey
                ? t('template.center.settingsDialog.git.sshKeys.actions.regenerate')
                : t('template.center.settingsDialog.git.sshKeys.actions.generate')}
            </Button>
          </div>
          {hasChanges && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
              {t('template.center.settingsDialog.git.sshKeys.unsavedChanges')}
            </p>
          )}
          {sshKeys?.publicKey && !hasChanges && (
            <p className="text-xs text-muted-foreground mt-2">
              {t('template.center.settingsDialog.git.sshKeys.regenerateWarning')}
            </p>
          )}

          {/* 使用說明 */}
          {!sshKeys?.publicKey && (
            <div className="rounded-lg border border-border bg-muted/50 p-4 mt-4">
              <h4 className="text-sm font-semibold mb-2">
                {t('template.center.settingsDialog.git.sshKeys.usageInstructions.title')}
              </h4>
              <ol className="text-sm text-muted-foreground space-y-1 list-decimal list-inside">
                {[0, 1, 2, 3].map((index) => (
                  <li key={index}>{t(`template.center.settingsDialog.git.sshKeys.usageInstructions.steps.${index}`)}</li>
                ))}
              </ol>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
