/**
 * 設定檢查對話框
 * 在新增工作區前檢查用戶是否完成必要的系統設定
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { CheckCircle2, XCircle, AlertTriangle, Settings } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { SettingsValidationResult } from '@/shared/services/userSettingsValidation';
import { ROUTES } from '@/shared/constants/routes';

interface SettingsCheckDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  validationResult: SettingsValidationResult | null;
  onProceed: () => void;
}

export const SettingsCheckDialog: React.FC<SettingsCheckDialogProps> = ({
  open,
  onOpenChange,
  validationResult,
  onProceed,
}) => {
  const { t } = useI18n();
  const navigate = useNavigate();

  if (!validationResult) {
    return null;
  }

  const handleGoToSettings = () => {
    onOpenChange(false);
    navigate(ROUTES.SETTINGS);
  };

  const handleProceed = () => {
    onOpenChange(false);
    onProceed();
  };

  const SettingItem: React.FC<{ 
    label: string; 
    isValid: boolean; 
  }> = ({ label, isValid }) => (
    <div className="flex items-center gap-3 py-2">
      {isValid ? (
        <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
      ) : (
        <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
      )}
      <span className={`text-sm ${isValid ? 'text-foreground' : 'text-muted-foreground'}`}>
        {label}
      </span>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {validationResult.isValid ? (
              <>
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                {t('dialogs.settingsCheck.title.ready')}
              </>
            ) : (
              <>
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                {t('dialogs.settingsCheck.title.incomplete')}
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {validationResult.isValid
              ? t('dialogs.settingsCheck.description.ready')
              : t('dialogs.settingsCheck.description.incomplete')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 設定檢查列表 */}
          <div className="rounded-lg border border-border bg-muted/30 p-4">
            <h4 className="text-sm font-medium mb-3">
              {t('dialogs.settingsCheck.requiredSettings')}
            </h4>
            <div className="space-y-1">
              <SettingItem
                label={t('dialogs.settingsCheck.settings.ssh')}
                isValid={validationResult.details.ssh}
              />
              <SettingItem
                label={t('dialogs.settingsCheck.settings.git')}
                isValid={validationResult.details.git}
              />
            </div>
          </div>

          {/* 警告訊息 */}
          {!validationResult.isValid && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {t('dialogs.settingsCheck.warning', {
                  settings: validationResult.missingSettings.join('、'),
                })}
              </AlertDescription>
            </Alert>
          )}

          {/* 提示訊息 */}
          {validationResult.isValid && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                {t('dialogs.settingsCheck.allComplete')}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          {!validationResult.isValid ? (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="w-full sm:w-auto"
              >
                {t('common.cancel')}
              </Button>
              <Button
                onClick={handleGoToSettings}
                className="w-full sm:w-auto"
              >
                <Settings className="mr-2 h-4 w-4" />
                {t('dialogs.settingsCheck.actions.goToSettings')}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="w-full sm:w-auto"
              >
                {t('common.cancel')}
              </Button>
              <Button
                onClick={handleProceed}
                className="w-full sm:w-auto"
              >
                {t('dialogs.settingsCheck.actions.proceed')}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SettingsCheckDialog;
