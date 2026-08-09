import React from 'react';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { KnowledgeBaseCreateDialog } from '../components/KnowledgeBaseCreateDialog';
import { KnowledgeBaseShellAdapter } from '../components/KnowledgeBaseShellAdapter';

interface KnowledgeBaseCreateRouteProps {
  navigationSlot?: React.ReactNode;
}

export const KnowledgeBaseCreateRoute: React.FC<KnowledgeBaseCreateRouteProps> = ({ navigationSlot }) => {
  const { t } = useI18n();
  const [open, setOpen] = React.useState(true);

  return (
    <KnowledgeBaseShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        main: {
          accessibleLabel: t('knowledgeBase.create.routeTitle'),
          content: (
            <div className="h-full overflow-auto p-6 md:p-8">
              <div className="mx-auto flex max-w-3xl flex-col gap-6">
                <div className="flex items-center justify-between">
                  <Button asChild variant="ghost" className="gap-2">
                    <Link to={ROUTES.knowledgeBase.root}>
                      <ArrowLeft className="h-4 w-4" />
                      {t('knowledgeBase.create.routeBack')}
                    </Link>
                  </Button>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-amber-500" />
                      {t('knowledgeBase.create.routeTitle')}
                    </CardTitle>
                    <CardDescription>{t('knowledgeBase.create.routeDescription')}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-lg border border-dashed bg-muted/40 p-4 text-sm text-muted-foreground">
                      {t('knowledgeBase.create.routeHint')}
                    </div>
                  </CardContent>
                </Card>
              </div>
              <KnowledgeBaseCreateDialog open={open} onOpenChange={setOpen} />
            </div>
          ),
        },
      }}
    />
  );
};
