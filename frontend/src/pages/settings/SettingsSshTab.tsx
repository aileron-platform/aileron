import React from 'react';
import { Key } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsSSH } from '@/shared/types/user';

interface SettingsSshTabProps {
  sshKeys: UserSettingsSSH;
  showPrivateKey: boolean;
  onSshKeysChange: (sshKeys: UserSettingsSSH) => void;
  onShowPrivateKeyChange: (showPrivateKey: boolean) => void;
  onCopyPrivateKey: () => void;
  onCopyPublicKey: () => void;
  onGenerateSSHKey: () => void;
}

export const SettingsSshTab: React.FC<SettingsSshTabProps> = ({
  sshKeys,
  showPrivateKey,
  onSshKeysChange,
  onShowPrivateKeyChange,
  onCopyPrivateKey,
  onCopyPublicKey,
  onGenerateSSHKey,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6 p-1">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            {t('pages.settings.sections.ssh.title')}
          </CardTitle>
          <CardDescription>{t('pages.settings.sections.ssh.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="privateKey">{t('pages.settings.sections.ssh.privateKey.label')}</Label>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => onShowPrivateKeyChange(!showPrivateKey)}>
                  {showPrivateKey
                    ? t('pages.settings.sections.ssh.privateKey.actions.hide')
                    : t('pages.settings.sections.ssh.privateKey.actions.show')}
                </Button>
                <Button variant="outline" size="sm" onClick={onCopyPrivateKey}>
                  {t('pages.settings.sections.ssh.privateKey.actions.copy')}
                </Button>
              </div>
            </div>
            <Textarea
              id="privateKey"
              placeholder={t('pages.settings.sections.ssh.privateKey.placeholder')}
              value={showPrivateKey ? (sshKeys.privateKey || '') : '••••••••••••'}
              onChange={(event) => onSshKeysChange({ ...sshKeys, privateKey: event.target.value })}
              className="font-mono text-sm"
              disabled={!showPrivateKey}
              rows={8}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="publicKey">{t('pages.settings.sections.ssh.publicKey.label')}</Label>
              <Button variant="outline" size="sm" onClick={onCopyPublicKey}>
                {t('pages.settings.sections.ssh.publicKey.copy')}
              </Button>
            </div>
            <Textarea
              id="publicKey"
              placeholder={t('pages.settings.sections.ssh.publicKey.placeholder')}
              value={sshKeys.publicKey || ''}
              onChange={(event) => onSshKeysChange({ ...sshKeys, publicKey: event.target.value })}
              className="font-mono text-sm"
              rows={4}
            />
          </div>
          <Button onClick={onGenerateSSHKey} variant="outline">
            {t('pages.settings.sections.ssh.generate')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};
