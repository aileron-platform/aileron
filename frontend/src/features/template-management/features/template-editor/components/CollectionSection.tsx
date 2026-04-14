import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import SectionCard from './SectionCard';
import { useI18n } from '@/shared/hooks/useI18n';

export interface BaseCollectionItem {
  localId: string;
}

export interface CollectionSectionConfig<T extends BaseCollectionItem> {
  title: string;
  description: string;
  items: T[];
  emptyHint: string;
  onItemsChange: (items: T[]) => void;
  renderFields: (item: T, onChange: (value: T) => void) => React.ReactNode;
  createItem: () => T;
}

const CollectionSectionInner = <T extends BaseCollectionItem>({ config }: { config: CollectionSectionConfig<T> }) => {
  const { t } = useI18n();
  const { title, description, items, emptyHint, onItemsChange, renderFields, createItem } = config;

  const handleAdd = () => {
    onItemsChange([...items, createItem()]);
  };

  const handleUpdate = (localId: string, value: T) => {
    onItemsChange(items.map(item => (item.localId === localId ? value : item)));
  };

  const handleRemove = (localId: string) => {
    onItemsChange(items.filter(item => item.localId !== localId));
  };

  return (
    <SectionCard
      title={title}
      description={description}
      action={
        <Button type="button" variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
          <Plus className="h-3.5 w-3.5 mr-1" /> {t('template.editor.collection.actions.add')}
        </Button>
      }
    >
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyHint}</p>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <Card key={item.localId} className="border border-border/50 bg-muted/20">
              <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
                <CardTitle className="text-sm font-medium text-foreground">
                  {t('template.editor.collection.itemTitle')}
                </CardTitle>
                <Button type="button" variant="ghost" size="icon" onClick={() => handleRemove(item.localId)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-3 px-4 pb-4">
                {renderFields(item, value => handleUpdate(item.localId, value))}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </SectionCard>
  );
};

export const renderCollectionSection = <T extends BaseCollectionItem>(config: CollectionSectionConfig<T>) => {
  return <CollectionSectionInner config={config} />;
};
