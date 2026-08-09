import React, { useMemo, useState } from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { Loader2, LogIn } from 'lucide-react';

import { useAuth } from '../hooks/useAuth';
import AuthLayout from '@/features/auth/components/AuthLayout';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { AUTH_ERROR_CODES, toAuthErrorCode } from '../model/authErrorCodes';

interface LocationState {
  from?: {
    pathname: string;
    search?: string;
    hash?: string;
  };
}

const toSafeDestination = (from: LocationState['from']): string | null => {
  if (!from?.pathname || !from.pathname.startsWith('/') || from.pathname.startsWith('//')) {
    return null;
  }
  return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`;
};

const getLoginErrorMessage = (
  errorCode: string | null,
  t: (key: string) => string,
): string | null => {
  if (!errorCode) return null;
  if (errorCode === AUTH_ERROR_CODES.configurationInvalid) {
    return t('pages.auth.login.error.configurationInvalid');
  }
  if (errorCode === AUTH_ERROR_CODES.stateExpired) {
    return t('pages.auth.login.error.sessionExpired');
  }
  return t('pages.auth.login.error.providerFailed');
};

const LoginPage: React.FC = () => {
  const { t } = useI18n();
  const { login, isAuthenticated, isLoading, error, clearError } = useAuth();
  const location = useLocation();
  const locationState = location.state as LocationState | null;
  const [formError, setFormError] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);

  const destination = useMemo(
    () => toSafeDestination(locationState?.from) ?? ROUTES.workspace.root,
    [locationState],
  );

  if (isAuthenticated) {
    return <Navigate to={destination} replace />;
  }

  const handleLogin = async () => {
    setIsRedirecting(true);
    clearError();
    try {
      await login();
    } catch (error) {
      setFormError(toAuthErrorCode(error, AUTH_ERROR_CODES.loginFailed));
    } finally {
      setIsRedirecting(false);
    }
  };

  const activeError = getLoginErrorMessage(formError ?? error, t);

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
          onClick={handleLogin}
          disabled={isLoading || isRedirecting}
        >
          {isRedirecting ? (
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
