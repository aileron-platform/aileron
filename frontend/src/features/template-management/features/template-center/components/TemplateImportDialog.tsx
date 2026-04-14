import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

export interface TemplateImportDialogProps {
  open: boolean;
  isImporting: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (file: File) => void;
}

export const TemplateImportDialog: React.FC<TemplateImportDialogProps> = ({
  open,
  isImporting,
  onOpenChange,
  onImport,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const { t } = useI18n();

  useEffect(() => {
    if (!open) {
      setSelectedFile(null);
    }
  }, [open]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleImport = () => {
    if (selectedFile) {
      onImport(selectedFile);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('template.center.import.title')}</DialogTitle>
          <DialogDescription>{t('template.center.import.description')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <input
              type="file"
              accept=".json,.mwtemplate,.zip"
              onChange={handleFileChange}
              className="w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-2 file:text-sm file:font-medium file:text-foreground hover:file:bg-muted/40"
            />
          </div>
          {selectedFile && (
            <div className="rounded border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
              {t('template.center.import.selectedFile', { name: selectedFile.name })}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isImporting}>
            {t('template.center.import.actions.cancel')}
          </Button>
          <Button onClick={handleImport} disabled={!selectedFile || isImporting}>
            {isImporting ? t('template.center.import.actions.importing') : t('template.center.import.actions.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TemplateImportDialog;
