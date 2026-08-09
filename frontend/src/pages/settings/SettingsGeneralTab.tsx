import React from 'react';
import { Globe, Monitor, Moon, Palette, Sun } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Separator } from '@/shared/components/ui/separator';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserSettingsGeneral } from '@/shared/types/user';

interface SettingsGeneralTabProps {
  generalSettings: UserSettingsGeneral;
  onGeneralSettingsChange: (settings: UserSettingsGeneral) => void;
  onThemeChange: (theme: UserSettingsGeneral['theme']) => void;
  onLanguageChange: (language: UserSettingsGeneral['language']) => void;
}

export const SettingsGeneralTab: React.FC<SettingsGeneralTabProps> = ({
  generalSettings,
  onGeneralSettingsChange,
  onThemeChange,
  onLanguageChange,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6 p-1">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            {t('pages.settings.sections.appearance.title')}
          </CardTitle>
          <CardDescription>{t('pages.settings.sections.appearance.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label>{t('pages.settings.sections.appearance.theme.label')}</Label>
              <p className="text-sm text-muted-foreground">{t('pages.settings.sections.appearance.theme.description')}</p>
            </div>
            <Select
              value={generalSettings.theme}
              onValueChange={(value: UserSettingsGeneral['theme']) => onThemeChange(value)}
            >
              <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="light">
                  <div className="flex items-center gap-2"><Sun className="h-4 w-4" />{t('pages.settings.sections.appearance.theme.options.light')}</div>
                </SelectItem>
                <SelectItem value="dark">
                  <div className="flex items-center gap-2"><Moon className="h-4 w-4" />{t('pages.settings.sections.appearance.theme.options.dark')}</div>
                </SelectItem>
                <SelectItem value="system">
                  <div className="flex items-center gap-2"><Monitor className="h-4 w-4" />{t('pages.settings.sections.appearance.theme.options.system')}</div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label>{t('pages.settings.sections.appearance.language.label')}</Label>
              <p className="text-sm text-muted-foreground">{t('pages.settings.sections.appearance.language.description')}</p>
            </div>
            <Select
              value={generalSettings.language}
              onValueChange={(value: UserSettingsGeneral['language']) => onLanguageChange(value)}
            >
              <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="zh-TW">
                  <div className="flex items-center gap-2"><Globe className="h-4 w-4" />{t('pages.settings.sections.appearance.language.options.zhTW')}</div>
                </SelectItem>
                <SelectItem value="en">
                  <div className="flex items-center gap-2"><Globe className="h-4 w-4" />{t('pages.settings.sections.appearance.language.options.en')}</div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label>{t('pages.settings.sections.appearance.timezone.label')}</Label>
              <p className="text-sm text-muted-foreground">{t('pages.settings.sections.appearance.timezone.description')}</p>
            </div>
            <Select
              value={generalSettings.timezone}
              onValueChange={(timezone) => onGeneralSettingsChange({ ...generalSettings, timezone })}
            >
              <SelectTrigger className="w-60"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="UTC">{t('pages.settings.sections.appearance.timezone.options.utc')}</SelectItem>
                <SelectItem value="Asia/Taipei">{t('pages.settings.sections.appearance.timezone.options.taipei')}</SelectItem>
                <SelectItem value="Asia/Tokyo">{t('pages.settings.sections.appearance.timezone.options.tokyo')}</SelectItem>
                <SelectItem value="Europe/London">{t('pages.settings.sections.appearance.timezone.options.london')}</SelectItem>
                <SelectItem value="America/Los_Angeles">{t('pages.settings.sections.appearance.timezone.options.losAngeles')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
