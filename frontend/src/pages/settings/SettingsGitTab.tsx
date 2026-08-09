import React from 'react';
import { GitBranch } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsGit } from '@/shared/types/user';

interface SettingsGitTabProps {
  gitSettings: UserSettingsGit;
  onGitSettingsChange: (settings: UserSettingsGit) => void;
}

export const SettingsGitTab: React.FC<SettingsGitTabProps> = ({
  gitSettings,
  onGitSettingsChange,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6 p-1">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            {t('pages.settings.sections.git.title')}
          </CardTitle>
          <CardDescription>{t('pages.settings.sections.git.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="gitUserName">{t('pages.settings.sections.git.userName.label')}</Label>
            <Input
              id="gitUserName"
              type="text"
              placeholder={t('pages.settings.sections.git.userName.placeholder')}
              value={gitSettings.userName || ''}
              onChange={(event) =>
                onGitSettingsChange({ ...gitSettings, userName: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="gitUserEmail">{t('pages.settings.sections.git.userEmail.label')}</Label>
            <Input
              id="gitUserEmail"
              type="email"
              placeholder={t('pages.settings.sections.git.userEmail.placeholder')}
              value={gitSettings.userEmail || ''}
              onChange={(event) =>
                onGitSettingsChange({ ...gitSettings, userEmail: event.target.value })
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
