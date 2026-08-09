import React, { useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import { Loader2, UserPlus } from 'lucide-react';

import { useAuth } from '../hooks/useAuth';
import AuthLayout from '@/features/auth/components/AuthLayout';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { AUTH_ERROR_CODES, toAuthErrorCode } from '../model/authErrorCodes';

const getRegistrationErrorMessage = (
  errorCode: string | null,
  t: (key: string) => string,
): string | null => {
  if (!errorCode) return null;
  if (errorCode === AUTH_ERROR_CODES.registrationUnavailable) {
    return t('pages.auth.register.error.providerUnavailable');
  }
  if (errorCode === AUTH_ERROR_CODES.configurationInvalid) {
    return t('pages.auth.register.error.configurationInvalid');
  }
  return t('pages.auth.register.error.registerFailed');
};

const RegisterPage: React.FC = () => {
  const { t } = useI18n();
  const { register, isAuthenticated, isLoading, error, clearError } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to={ROUTES.workspace.root} replace />;
  }

  const handleRegister = () => {
    setIsRedirecting(true);
    clearError();
    try {
      register();
    } catch (error) {
      setFormError(toAuthErrorCode(error, AUTH_ERROR_CODES.registrationFailed));
      setIsRedirecting(false);
    }
  };

  const activeError = getRegistrationErrorMessage(formError ?? error, t);

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
