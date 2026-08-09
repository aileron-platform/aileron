import React from 'react';
import { CheckCircle2, GitBranch } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

export interface MarketplaceFirstRunOnboardingProps {
  rootPath: string;
  canManageRegistry: boolean;
  onInitialize: () => void;
  onClone: () => void;
}

export const MarketplaceFirstRunOnboarding: React.FC<MarketplaceFirstRunOnboardingProps> = ({
  rootPath,
  canManageRegistry,
  onInitialize,
  onClone,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
      <FeatureHeader
        title={t('marketplace.onboarding.title')}
        icon={GitBranch}
        info={<div className="text-xs text-muted-foreground">{t('marketplace.onboarding.description')}</div>}
      />
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-6 rounded-lg border border-border bg-background p-6">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold">{t('marketplace.onboarding.setupTitle')}</h2>
            <p className="text-sm text-muted-foreground">{t('marketplace.onboarding.setupDescription')}</p>
          </div>
          <Alert>
            <CheckCircle2 className="h-4 w-4" />
            <AlertDescription>
              {t('marketplace.onboarding.rootPath', { path: rootPath })}
            </AlertDescription>
          </Alert>
          {canManageRegistry ? (
            <div className="grid gap-3 md:grid-cols-2">
              <Button className="h-auto justify-start p-4 text-left" onClick={onInitialize}>
                <div>
                  <div className="font-medium">{t('marketplace.onboarding.actions.initialize')}</div>
                  <div className="mt-1 text-xs opacity-80">{t('marketplace.onboarding.actions.initializeDescription')}</div>
                </div>
              </Button>
              <Button variant="outline" className="h-auto justify-start p-4 text-left" onClick={onClone}>
                <div>
                  <div className="font-medium">{t('marketplace.onboarding.actions.clone')}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{t('marketplace.onboarding.actions.cloneDescription')}</div>
                </div>
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t('common.authorization.accessDeniedDescription')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
