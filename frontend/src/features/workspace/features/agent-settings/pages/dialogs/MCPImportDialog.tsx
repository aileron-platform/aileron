import React, { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Alert, AlertDescription } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { AlertCircle, Info, Upload, CheckCircle, FileText, File, X } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

type McpScope = 'project' | 'user' | 'local';

interface ImportResult {
  created: string[];
  updated: string[];
  skipped: string[];
}

const DEFAULT_IMPORT_SCOPES: McpScope[] = ['project', 'user', 'local'];

interface MCPImportDialogProps {
  open: boolean;
  onClose: () => void;
  onImport: (options: { scope: McpScope; file: File; overwrite?: boolean }) => Promise<ImportResult>;
  availableScopes?: readonly string[];
  i18nNamespace?: string;
}

const MCPImportDialog: React.FC<MCPImportDialogProps> = ({ open, onClose, onImport, availableScopes, i18nNamespace = 'workspace.claudeCode' }) => {
  // 過濾掉 plugin（import 不支援 plugin scope），只保留有效的 McpScope
  const importScopes: McpScope[] = availableScopes
    ? (availableScopes.filter((s): s is McpScope => s === 'project' || s === 'user' || s === 'local'))
    : DEFAULT_IMPORT_SCOPES;
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [formData, setFormData] = useState<{ scope: McpScope }>({ scope: importScopes[0] ?? 'project' });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { t } = useI18n();

  const resetForm = () => {
    setFormData({ scope: importScopes[0] ?? 'project' });
    setSelectedFile(null);
    setError(null);
    setImportResult(null);
    setIsDragOver(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileSelect = (file: File) => {
    if (!file.name.endsWith('.json')) {
      setError(t(`${i18nNamespace}.mcp.dialogs.import.errors.invalidFile`));
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError(t(`${i18nNamespace}.mcp.dialogs.import.errors.fileTooLarge`));
      return;
    }

    setSelectedFile(file);
    setError(null);
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);

    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setError(t(`${i18nNamespace}.mcp.dialogs.import.errors.noFile`));
      return;
    }

    setIsLoading(true);
    setError(null);
    setImportResult(null);

    try {
      const result = await onImport({ scope: formData.scope, file: selectedFile, overwrite: false });
      setImportResult(result);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    onClose();
    resetForm();
  };

  const resultEntries = importResult
    ? [
        ...importResult.created.map((name) => ({ name, status: 'created' as const })),
        ...importResult.updated.map((name) => ({ name, status: 'updated' as const })),
        ...importResult.skipped.map((name) => ({ name, status: 'skipped' as const })),
      ]
    : [];

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg max-h-[90vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            {t(`${i18nNamespace}.mcp.dialogs.import.title`)}
          </DialogTitle>
          <DialogDescription>
            {t(`${i18nNamespace}.mcp.dialogs.import.description`)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 px-6 py-4 min-h-0">
          {!importResult && (
            <>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  {t(`${i18nNamespace}.mcp.dialogs.import.info.upload`)}
                  <Badge variant="outline" className="mx-1">.mcp.json</Badge>
                  {t(`${i18nNamespace}.mcp.dialogs.import.info.description`)}
                </AlertDescription>
              </Alert>

              <div className="space-y-3">
                <Label>{t(`${i18nNamespace}.mcp.dialogs.import.fields.file.label`)} *</Label>

                <div
                  className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
                    isDragOver
                      ? 'border-primary bg-primary/5'
                      : selectedFile
                        ? 'border-green-500 bg-green-50'
                        : 'border-muted-foreground/25 hover:border-primary/50'
                  }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json"
                    onChange={handleFileInputChange}
                    className="hidden"
                  />

                  {selectedFile ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-center gap-2">
                        <File className="h-8 w-8 text-green-600" />
                        <CheckCircle className="h-5 w-5 text-green-600" />
                      </div>
                      <div>
                        <p className="font-medium text-green-700">{selectedFile.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {(selectedFile.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedFile(null);
                          if (fileInputRef.current) {
                            fileInputRef.current.value = '';
                          }
                        }}
                        disabled={isLoading}
                      >
                        <X className="h-4 w-4 mr-1" />
                        {t(`${i18nNamespace}.mcp.dialogs.import.actions.removeFile`)}
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
                      <div>
                        <p className="font-medium">{t(`${i18nNamespace}.mcp.dialogs.import.fields.file.dragText`)}</p>
                        <p className="text-sm text-muted-foreground">
                          {t(`${i18nNamespace}.mcp.dialogs.import.fields.file.formatInfo`)}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="scope">{t(`${i18nNamespace}.mcp.dialogs.import.fields.scope.label`)} *</Label>
                <Select
                  value={formData.scope}
                  onValueChange={(value: McpScope) =>
                    setFormData({ ...formData, scope: value })
                  }
                  disabled={isLoading}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper" side="bottom" align="start" sideOffset={4}>
                    {importScopes.map((s) => (
                      <SelectItem key={s} value={s}>
                        <div>
                          <div className="font-medium">{t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.options.${s}.title`)}</div>
                          <div className="text-xs text-muted-foreground">{t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.options.${s}.description`)}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {t(`${i18nNamespace}.mcp.dialogs.import.fields.scope.helper`)}
                </p>
              </div>

              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <strong>{t(`${i18nNamespace}.mcp.dialogs.import.warning.title`)}：</strong>
                  {t(`${i18nNamespace}.mcp.dialogs.import.warning.message`)}
                </AlertDescription>
              </Alert>
            </>
          )}

          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-primary" />
              <span>{t(`${i18nNamespace}.mcp.dialogs.import.progress.importing`)}</span>
            </div>
          )}

          {importResult && (
            <div className="space-y-4">
              <div className="rounded-lg bg-muted p-4">
                <h4 className="mb-3 font-medium">{t(`${i18nNamespace}.mcp.dialogs.import.result.title`)}</h4>

                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold text-green-600">{importResult.created.length}</div>
                    <div className="text-sm text-muted-foreground">
                      {t(`${i18nNamespace}.mcp.dialogs.import.result.created`, { defaultValue: '新增' })}
                    </div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">{importResult.updated.length}</div>
                    <div className="text-sm text-muted-foreground">
                      {t(`${i18nNamespace}.mcp.dialogs.import.result.updated`, { defaultValue: '更新' })}
                    </div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-amber-600">{importResult.skipped.length}</div>
                    <div className="text-sm text-muted-foreground">
                      {t(`${i18nNamespace}.mcp.dialogs.import.result.skipped`, { defaultValue: '跳過' })}
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <h5 className="font-medium">{t(`${i18nNamespace}.mcp.dialogs.import.result.details`)}</h5>
                {resultEntries.length > 0 ? (
                  <div className="max-h-40 overflow-y-auto space-y-2">
                    {resultEntries.map((entry) => (
                      <div
                        key={`${entry.status}-${entry.name}`}
                        className={`flex items-center gap-3 rounded border p-2 ${
                          entry.status === 'skipped'
                            ? 'border-amber-200 bg-amber-50'
                            : entry.status === 'updated'
                              ? 'border-blue-200 bg-blue-50'
                              : 'border-green-200 bg-green-50'
                        }`}
                      >
                        {entry.status === 'skipped' ? (
                          <AlertCircle className="h-4 w-4 text-amber-600" />
                        ) : (
                          <CheckCircle
                            className={`h-4 w-4 ${
                              entry.status === 'updated' ? 'text-blue-600' : 'text-green-600'
                            }`}
                          />
                        )}
                        <div className="flex-1">
                          <div className="text-sm font-medium">{entry.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {entry.status === 'created'
                              ? t(`${i18nNamespace}.mcp.dialogs.import.result.created`, {
                                  defaultValue: '新增',
                                })
                              : entry.status === 'updated'
                              ? t(`${i18nNamespace}.mcp.dialogs.import.result.updated`, {
                                  defaultValue: '更新',
                                })
                              : t(`${i18nNamespace}.mcp.dialogs.import.result.skipped`, {
                                  defaultValue: '已跳過',
                                })}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Alert>
                    <FileText className="h-4 w-4" />
                    <AlertDescription>
                      {t(`${i18nNamespace}.mcp.dialogs.import.result.noServers`)}
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="flex-shrink-0 border-t pt-4 px-6 pb-6">
          {!importResult ? (
            <>
              <Button
                variant="outline"
                onClick={handleClose}
                disabled={isLoading}
              >
                {t('common.cancel')}
              </Button>
              <Button
                onClick={handleImport}
                disabled={isLoading || !selectedFile}
              >
                {isLoading ? t(`${i18nNamespace}.mcp.dialogs.import.actions.importing`) : t(`${i18nNamespace}.mcp.dialogs.import.actions.startImport`)}
              </Button>
            </>
          ) : (
            <Button onClick={handleClose}>
              {t('common.close')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MCPImportDialog;
