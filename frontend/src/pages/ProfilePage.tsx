import React, { useEffect, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('ProfilePage');
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Label } from '@/shared/components/ui/label';
import { UserCircle, Save, Upload, Mail } from 'lucide-react';
import GlobalNavigation from '@/shared/components/navigation/GlobalNavigation';
import { useI18n } from '@/shared/hooks/useI18n';
import { useApp } from '@/app/providers/AppProvider';
import { apiClient } from '@/shared/api/apiClient';
import type { UserProfile, UserProfileResponse } from '@/shared/types/user';

export const ProfilePage: React.FC = () => {
  const { state: appState } = useApp();
  const userId = appState.user.id;
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();

  useEffect(() => {
    let isMounted = true;

    const fetchProfile = async () => {
      if (!userId) {
        if (isMounted) {
          setError(t('pages.profile.errors.notLoggedIn'));
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.get<UserProfileResponse>(`/users/${userId}/profile`);
        if (isMounted) {
          setProfile(response.data);
        }
      } catch (err) {
        logger.error('load failed', { error: err });
        if (isMounted) {
          setError(t('pages.profile.notifications.loadFailed'));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void fetchProfile();

    return () => {
      isMounted = false;
    };
  }, [t, userId]);

  const handleSave = async () => {
    if (!userId) {
      setError(t('pages.profile.errors.notLoggedIn'));
      return;
    }
    if (!profile) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await apiClient.put<UserProfileResponse>(`/users/${userId}/profile`, {
        firstName: profile.firstName,
        lastName: profile.lastName,
        avatarUrl: profile.avatarUrl,
      });

      setProfile(response.data);
      setIsEditing(false);
    } catch (err) {
      logger.error('save failed', { error: err });
      setError(t('pages.profile.notifications.saveFailed'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleAvatarUpload = () => {
    // TODO: 實作頭像上傳功能
    logger.debug('Upload avatar');
  };

  const fullName = profile ? `${profile.firstName} ${profile.lastName}`.trim() : '';

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <GlobalNavigation />
      <div className="flex-1 overflow-auto">
        <div className="container mx-auto py-8 px-6 max-w-3xl space-y-6">
          {/* 頁面標題 */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">{t('pages.profile.title')}</h1>
              <p className="text-muted-foreground mt-1">{t('pages.profile.subtitle')}</p>
            </div>
            <div className="flex items-center gap-3">
              {isEditing ? (
                <>
                  <Button
                    variant="outline"
                    onClick={() => setIsEditing(false)}
                    disabled={isSaving}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="gap-2"
                  >
                    <Save className="h-4 w-4" />
                    {isSaving ? t('pages.profile.actions.saving') : t('pages.profile.actions.save')}
                  </Button>
                </>
              ) : (
                <Button onClick={() => setIsEditing(true)} disabled={isLoading || !profile}>
                  {t('pages.profile.actions.edit')}
                </Button>
              )}
            </div>
          </div>

          {error && (
            <div role="alert" className="rounded-md border border-destructive bg-destructive/10 text-destructive px-4 py-3">
              {error}
            </div>
          )}

          {isLoading && (
            <div className="rounded-md border border-border px-4 py-6 text-muted-foreground">
              {t('pages.profile.status.loading')}
            </div>
          )}

          {!isLoading && profile && (
            <Card>
              <CardHeader>
                <CardTitle>{t('pages.profile.sections.personalInfo.title')}</CardTitle>
                <CardDescription>
                  {t('pages.profile.sections.personalInfo.description')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 頭像區 */}
                <div className="flex items-center gap-6">
                  <div className="relative">
                    <Avatar className="h-20 w-20 ring-4 ring-primary/20">
                      <AvatarImage src={profile.avatarUrl ?? undefined} alt={fullName} />
                      <AvatarFallback
                        className="bg-primary text-primary-foreground text-xl"
                        style={{ background: 'hsl(var(--primary))' }}
                      >
                        <UserCircle className="h-8 w-8" />
                      </AvatarFallback>
                    </Avatar>
                    {isEditing && (
                      <Button
                        size="sm"
                        variant="secondary"
                        className="absolute -bottom-1 -right-1 rounded-full h-7 w-7 p-0"
                        onClick={handleAvatarUpload}
                      >
                        <Upload className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">{fullName || profile.username}</h3>
                    <p className="text-sm text-muted-foreground">@{profile.username}</p>
                    <div className="flex items-center gap-1.5 mt-1 text-sm text-muted-foreground">
                      <Mail className="h-3.5 w-3.5" />
                      <span>{profile.email}</span>
                    </div>
                  </div>
                </div>

                {/* 帳號資訊（唯讀） */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="username">{t('pages.profile.fields.username.label')}</Label>
                    <Input
                      id="username"
                      value={profile.username}
                      disabled
                      className="bg-muted"
                    />
                    <p className="text-xs text-muted-foreground">{t('pages.profile.fields.username.cannotChange')}</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">{t('pages.profile.fields.email.label')}</Label>
                    <Input
                      id="email"
                      type="email"
                      value={profile.email}
                      disabled
                      className="bg-muted"
                    />
                    <p className="text-xs text-muted-foreground">{t('pages.profile.fields.email.keycloakNote')}</p>
                  </div>
                </div>

                {/* 姓名（可編輯） */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="firstName">{t('pages.profile.fields.firstName.label')}</Label>
                    <Input
                      id="firstName"
                      value={profile.firstName}
                      onChange={(e) =>
                        setProfile(prev => (prev ? { ...prev, firstName: e.target.value } : prev))
                      }
                      disabled={!isEditing}
                      placeholder={t('pages.profile.fields.firstName.placeholder')}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="lastName">{t('pages.profile.fields.lastName.label')}</Label>
                    <Input
                      id="lastName"
                      value={profile.lastName}
                      onChange={(e) =>
                        setProfile(prev => (prev ? { ...prev, lastName: e.target.value } : prev))
                      }
                      disabled={!isEditing}
                      placeholder={t('pages.profile.fields.lastName.placeholder')}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
