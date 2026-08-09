import type React from 'react';
import { ShieldAlert } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

export const AuthorizationDeniedState: React.FC = () => {
  const { t } = useI18n();

  return (
    <div
      role="alert"
      className="flex h-full min-h-[24rem] items-center justify-center bg-background px-6"
    >
      <div className="max-w-md text-center">
        <ShieldAlert
          aria-hidden="true"
          className="mx-auto mb-4 h-10 w-10 text-muted-foreground"
        />
        <h1 className="text-xl font-semibold text-foreground">
          {t('common.authorization.accessDeniedTitle')}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {t('common.authorization.accessDeniedDescription')}
        </p>
      </div>
    </div>
  );
};
