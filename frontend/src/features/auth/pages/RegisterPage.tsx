import React, { useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import { Loader2, UserPlus } from 'lucide-react';

import { useAuth } from '../hooks/useAuth';
import AuthLayout from '@/features/auth/components/AuthLayout';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

const RegisterPage: React.FC = () => {
  const { t } = useI18n();
  const { registerWithKeycloak, isAuthenticated, isLoading, error, clearError } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/workspaces" replace />;
  }

  const handleRegister = () => {
    setIsRedirecting(true);
    clearError();
    try {
      registerWithKeycloak();
    } catch (error) {
      const message = error instanceof Error ? error.message : t('pages.auth.register.error.registerFailed');
      setFormError(message);
      setIsRedirecting(false);
    }
  };

  const activeError = formError ?? error;

  return (
    <AuthLayout
      title={t('pages.auth.register.title')}
      description={t('pages.auth.register.description')}
      footer={
        <span>
          {t('pages.auth.register.footer.hasAccount')}{' '}
          <Link to="/login" className="font-medium text-primary hover:underline">
            {t('pages.auth.register.footer.login')}
          </Link>
        </span>
      }
    >
      <div className="space-y-6">
        {activeError ? (
          <Alert variant="destructive">
            <AlertTitle>{t('pages.auth.register.error.title')}</AlertTitle>
            <AlertDescription>{activeError}</AlertDescription>
          </Alert>
        ) : null}

        <Button
          type="button"
          variant="default"
          className="w-full bg-primary hover:bg-primary/90"
          onClick={handleRegister}
          disabled={isLoading || isRedirecting}
        >
          {isRedirecting ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('pages.auth.register.button.redirecting')}
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <UserPlus className="h-4 w-4" />
              {t('pages.auth.register.button.register')}
            </span>
          )}
        </Button>

        <div className="text-center text-sm text-muted-foreground">
          {t('pages.auth.register.hint')}
        </div>
      </div>
    </AuthLayout>
  );
};

export default RegisterPage;
