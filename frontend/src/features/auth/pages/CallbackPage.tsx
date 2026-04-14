/**
 * OAuth2 Callback Page
 *
 * Handles OAuth2/OIDC callback from Keycloak.
 * Extracts authorization code and state from URL parameters,
 * exchanges code for tokens, and redirects to destination.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, Loader2 } from 'lucide-react';

import { useAuth } from '../hooks/useAuth';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { useI18n } from '@/shared/hooks/useI18n';

const CallbackPage: React.FC = () => {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleKeycloakCallback } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);
  // 防止 React 18 Strict Mode 雙重執行 effect 導致 authorization code 被使用兩次
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processCallback = async () => {
      // Extract OAuth2 callback parameters
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Handle OAuth2 errors
      if (errorParam) {
        setError(errorDescription || errorParam);
        setIsProcessing(false);
        return;
      }

      // Validate required parameters
      if (!code || !state) {
        setError(t('pages.auth.callback.error.invalidCallback'));
        setIsProcessing(false);
        return;
      }

      try {
        // Exchange authorization code for tokens
        await handleKeycloakCallback(code, state);

        setIsProcessing(false);
        navigate('/workspaces', { replace: true });
      } catch (err) {
        const message = err instanceof Error ? err.message : t('pages.auth.callback.error.authFailed');
        setError(message);
        setIsProcessing(false);
      }
    };

    processCallback();
  }, [searchParams, handleKeycloakCallback, navigate]);

  if (isProcessing) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <LoadingSpinner label={t('pages.auth.callback.loading.label')} size="lg" />
          <p className="text-sm text-muted-foreground">{t('pages.auth.callback.loading.message')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-4">
        <div className="max-w-md space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('pages.auth.callback.error.title')}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>

          <div className="flex gap-2">
            <button
              onClick={() => navigate('/login', { replace: true })}
              className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t('pages.auth.callback.error.backToLogin')}
            </button>
            <button
              onClick={() => window.location.reload()}
              className="flex-1 rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent"
            >
              {t('pages.auth.callback.error.retry')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default CallbackPage;
