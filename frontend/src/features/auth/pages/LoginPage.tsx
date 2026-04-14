import React, { useMemo, useState } from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { Loader2, LogIn } from 'lucide-react';

import { useAuth } from '../hooks/useAuth';
import AuthLayout from '@/features/auth/components/AuthLayout';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

interface LocationState {
  from?: {
    pathname: string;
  };
}

const LoginPage: React.FC = () => {
  const { t } = useI18n();
  const { loginWithKeycloak, isAuthenticated, isLoading, error, clearError } = useAuth();
  const location = useLocation();
  const locationState = location.state as LocationState | null;
  const [formError, setFormError] = useState<string | null>(null);
  const [isKeycloakLogin, setIsKeycloakLogin] = useState(false);

  const destination = useMemo(() => locationState?.from?.pathname ?? '/workspaces', [locationState]);

  if (isAuthenticated) {
    return <Navigate to={destination} replace />;
  }

  const handleKeycloakLogin = () => {
    setIsKeycloakLogin(true);
    clearError();
    try {
      loginWithKeycloak();
    } catch (error) {
      const message = error instanceof Error ? error.message : t('pages.auth.login.error.keycloakFailed');
      setFormError(message);
      setIsKeycloakLogin(false);
    }
  };

  const activeError = formError ?? error;

  return (
    <AuthLayout
      title={t('pages.auth.login.title')}
      description={t('pages.auth.login.description')}
      footer={
        <span>
          {t('pages.auth.login.footer.noAccount')}{' '}
          <Link to="/register" className="font-medium text-primary hover:underline">
            {t('pages.auth.login.footer.register')}
          </Link>
        </span>
      }
    >
      <div className="space-y-6">
        {activeError ? (
          <Alert variant="destructive">
            <AlertTitle>{t('pages.auth.login.error.title')}</AlertTitle>
            <AlertDescription>{activeError}</AlertDescription>
          </Alert>
        ) : null}

        <Button
          type="button"
          variant="default"
          className="w-full bg-primary hover:bg-primary/90"
          onClick={handleKeycloakLogin}
          disabled={isLoading || isKeycloakLogin}
        >
          {isKeycloakLogin ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('pages.auth.login.button.redirecting')}
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <LogIn className="h-4 w-4" />
              {t('pages.auth.login.button.signIn')}
            </span>
          )}
        </Button>

        <div className="text-center text-sm text-muted-foreground">
          {t('pages.auth.login.hint')}
        </div>
      </div>
    </AuthLayout>
  );
};

export default LoginPage;
