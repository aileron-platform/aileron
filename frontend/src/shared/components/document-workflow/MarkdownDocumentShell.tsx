import React from 'react';
import { FileText, Loader2, RefreshCw, Save } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { MarkdownEditor } from '@/shared/components/composite/MarkdownEditor';

export interface MarkdownDocumentShellProps {
  title: string;
  refreshLabel: string;
  saveLabel: string;
  runtimeLoadingLabel: string;
  loadingLabel: string;
  runtimeStatusMessage?: string | null;
  runtimeLoading?: boolean;
  isRuntimeReady: boolean;
  isLoading?: boolean;
  isSaving?: boolean;
  isStale?: boolean;
  statusMessage?: React.ReactNode;
  staleMessage?: React.ReactNode;
  value: string;
  onChange: (value: string) => void;
  onRefresh: () => void;
  onSave: () => void;
  refreshDisabled?: boolean;
  saveDisabled?: boolean;
  headerExtras?: React.ReactNode;
  footerExtras?: React.ReactNode;
  placeholder?: string;
}

export const MarkdownDocumentShell: React.FC<MarkdownDocumentShellProps> = ({
  title,
  refreshLabel,
  saveLabel,
  runtimeLoadingLabel,
  loadingLabel,
  runtimeStatusMessage = null,
  runtimeLoading = false,
  isRuntimeReady,
  isLoading = false,
  isSaving = false,
  isStale = false,
  statusMessage,
  staleMessage,
  value,
  onChange,
  onRefresh,
  onSave,
  refreshDisabled = false,
  saveDisabled = false,
  headerExtras,
  footerExtras,
  placeholder,
}) => {
  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={title}
        icon={FileText}
        actions={
          <div className="flex items-center gap-2">
            {headerExtras}
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={onRefresh}
              disabled={refreshDisabled}
            >
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              {refreshLabel}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-xs"
              onClick={onSave}
              disabled={saveDisabled}
            >
              {isSaving ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="mr-1.5 h-3.5 w-3.5" />
              )}
              {saveLabel}
            </Button>
          </div>
        }
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        {runtimeLoading ? (
          <LoadingSpinner size="md" className="flex-1" text={runtimeLoadingLabel} />
        ) : !isRuntimeReady ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
            <p>{runtimeStatusMessage}</p>
          </div>
        ) : isLoading ? (
          <LoadingSpinner size="md" className="flex-1" text={loadingLabel} />
        ) : (
          <div className="flex flex-1 flex-col overflow-hidden">
            {isStale && staleMessage ? (
              <Alert className="mx-4 mt-4">
                <AlertDescription>{staleMessage}</AlertDescription>
              </Alert>
            ) : null}
            <MarkdownEditor
              value={value}
              onChange={onChange}
              className="flex-1"
              statusMessage={statusMessage}
              footerExtras={footerExtras}
              placeholder={placeholder}
            />
          </div>
        )}
      </div>
    </div>
  );
};

MarkdownDocumentShell.displayName = 'MarkdownDocumentShell';

export default MarkdownDocumentShell;
