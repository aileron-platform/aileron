import React from 'react';
import { Search, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';

interface PluginSearchBarProps {
  value: string;
  placeholder: string;
  label: string;
  clearLabel: string;
  onChange: (value: string) => void;
}

export const PluginSearchBar: React.FC<PluginSearchBarProps> = ({
  value,
  placeholder,
  label,
  clearLabel,
  onChange,
}) => (
  <div className="flex w-full gap-2 lg:max-w-md">
    <div className="relative min-w-0 flex-1">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={label}
        className="pl-9"
      />
    </div>
    {value.trim() ? (
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-10 shrink-0 px-3"
        onClick={() => onChange('')}
      >
        <X className="mr-1 h-4 w-4" />
        {clearLabel}
      </Button>
    ) : null}
  </div>
);
