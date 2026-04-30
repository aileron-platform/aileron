import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, FileCode2, Layers3, TriangleAlert } from 'lucide-react';

import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useI18n } from '@/shared/hooks/useI18n';
import type { CliType } from '@/shared/types/templates';
import {
  getTemplateCompilePreview,
  type TemplateCompileIssue,
  type TemplateCompilePreview,
} from '@/features/template-management/api/templateApi';

interface TargetPreviewTabContentProps {
  templateId: string;
  defaultTarget?: CliType;
}

const TARGETS: CliType[] = ['claude-code', 'codex', 'gemini', 'opencode'];

const getTargetLabelKey = (target: CliType): string => {
  switch (target) {
    case 'claude-code':
      return 'template.common.targets.claudeCode';
    case 'codex':
      return 'template.common.targets.codex';
    case 'gemini':
      return 'template.common.targets.gemini';
    case 'opencode':
      return 'template.common.targets.opencode';
    default:
      return target;
  }
};

const IssueList: React.FC<{
  title: string;
  items: TemplateCompileIssue[];
  emptyLabel: string;
}> = ({ title, items, emptyLabel }) => (
  <Card>
    <CardHeader className="pb-3">
      <CardTitle className="text-base">{title}</CardTitle>
    </CardHeader>
    <CardContent>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={`${item.feature}-${index}`} className="rounded-md border p-3">
              <div className="flex items-center gap-2">
                <Badge variant="outline">{item.feature}</Badge>
                <span className="text-xs text-muted-foreground">{item.target}</span>
              </div>
              <p className="mt-2 text-sm text-foreground">{item.message}</p>
            </div>
          ))}
        </div>
      )}
    </CardContent>
  </Card>
);

export const TargetPreviewTabContent: React.FC<TargetPreviewTabContentProps> = ({
  templateId,
  defaultTarget = 'claude-code',
}) => {
  const { t } = useI18n();
  const [target, setTarget] = useState<CliType>(defaultTarget);
  const [preview, setPreview] = useState<TemplateCompilePreview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const loadPreview = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await getTemplateCompilePreview(templateId, target);
        if (!active) return;
        setPreview(result);
      } catch (err) {
        if (!active) return;
        setPreview(null);
        setError(err instanceof Error ? err.message : t('template.detail.targetPreview.errors.loadFailed'));
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    void loadPreview();

    return () => {
      active = false;
    };
  }, [target, templateId, t]);

  const summary = useMemo(
    () => ({
      fileCount: preview?.files.length ?? 0,
      warningCount: preview?.warnings.length ?? 0,
      unsupportedCount: preview?.unsupported.length ?? 0,
      degradationCount: preview?.degradationNotes.length ?? 0,
    }),
    [preview],
  );

  return (
    <div className="h-full overflow-auto p-6">
      <div className="space-y-6">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                {t('template.detail.targetPreview.targetLabel')}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('template.detail.targetPreview.description')}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {TARGETS.map((candidate) => (
                <Button
                  key={candidate}
                  size="sm"
                  variant={candidate === target ? 'default' : 'outline'}
                  className="h-8 px-3 text-xs"
                  onClick={() => setTarget(candidate)}
                >
                  {t(getTargetLabelKey(candidate))}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary" className="gap-1">
              <FileCode2 className="h-3.5 w-3.5" />
              {t('template.detail.targetPreview.sections.files')} {summary.fileCount}
            </Badge>
            <Badge variant="outline" className="gap-1">
              <TriangleAlert className="h-3.5 w-3.5" />
              {t('template.detail.targetPreview.sections.warnings')} {summary.warningCount}
            </Badge>
            <Badge variant="outline" className="gap-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              {t('template.detail.targetPreview.sections.unsupported')} {summary.unsupportedCount}
            </Badge>
            <Badge variant="outline" className="gap-1">
              <Layers3 className="h-3.5 w-3.5" />
              {t('template.detail.targetPreview.sections.degradation')} {summary.degradationCount}
            </Badge>
          </div>
        </div>

        {isLoading && (
          <div className="text-sm text-muted-foreground">
            {t('template.detail.targetPreview.loading')}
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {!isLoading && !error && (
          <>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>{t('template.detail.targetPreview.sections.files')}</CardTitle>
                <CardDescription>
                  {preview?.target ? t(getTargetLabelKey(preview.target)) : ''}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!preview || preview.files.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t('template.detail.targetPreview.emptyFiles')}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {preview.files.map((file) => (
                      <div key={`${file.path}-${file.source}`} className="rounded-md border p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge>{file.path}</Badge>
                          <span className="text-xs text-muted-foreground">
                            {t('template.detail.targetPreview.file.sourceLabel')}: {file.source}
                          </span>
                        </div>
                        <div className="mt-3">
                          <p className="mb-2 text-xs font-medium text-muted-foreground">
                            {t('template.detail.targetPreview.file.contentPreviewLabel')}
                          </p>
                          <pre className="max-h-48 overflow-auto rounded bg-muted/40 p-3 text-xs text-foreground whitespace-pre-wrap break-words">
                            {file.content}
                          </pre>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-3">
              <IssueList
                title={t('template.detail.targetPreview.sections.warnings')}
                items={preview?.warnings ?? []}
                emptyLabel={t('template.detail.targetPreview.states.none')}
              />
              <IssueList
                title={t('template.detail.targetPreview.sections.unsupported')}
                items={preview?.unsupported ?? []}
                emptyLabel={t('template.detail.targetPreview.states.none')}
              />
              <IssueList
                title={t('template.detail.targetPreview.sections.degradation')}
                items={preview?.degradationNotes ?? []}
                emptyLabel={t('template.detail.targetPreview.states.none')}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default TargetPreviewTabContent;
