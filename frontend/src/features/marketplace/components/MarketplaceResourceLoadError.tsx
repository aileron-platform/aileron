import React from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplaceResourceLoadErrorProps {
  onRetry: () => void;
  className?: string;
}

export const MarketplaceResourceLoadError: React.FC<MarketplaceResourceLoadErrorProps> = ({
  onRetry,
  className = 'h-full',
}) => {
  const { t } = useI18n();

  return (
    <div className={`flex ${className} flex-col items-center justify-center gap-3 p-6 text-center`}>
      <AlertCircle className="h-6 w-6 text-destructive" />
      <p className="text-sm text-muted-foreground">
        {t('marketplace.common.resourceLoadError')}
      </p>
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>
        {t('marketplace.common.actions.retry')}
      </Button>
    </div>
  );
};
