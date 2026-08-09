import React, { useState, useMemo } from 'react';
import {
  Bot,
  Brush,
  Check,
  Code,
  Database,
  Feather,
  FileText,
  Globe,
  Image,
  LayoutDashboard,
  MessageSquare,
  Monitor,
  Palette,
  Search,
  Settings,
  Shield,
  Smartphone,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  cleanupAnswers,
  computeVisibleQuestions,
  formatFormAnswers,
  resolveQuestionOptions,
} from '../../model/questionFormModel';
import type { QuestionForm, FormQuestion, OptionCard } from '../../model/questionFormModel';

interface QuestionFormViewProps {
  form: QuestionForm;
  interactive: boolean;
  submittedAnswers?: Record<string, string | string[]> | null;
  isSubmitting?: boolean;
  errorKey?: string | null;
  onSubmit?: (formattedText: string, answers: Record<string, string | string[]>) => void;
}

const HEX_RE = /^#[0-9a-fA-F]{6}$/;

function normalizeHex(value: string): string {
  return HEX_RE.test(value) ? value.toLowerCase() : '';
}

function kebabToPascal(name: string): string {
  return name
    .split('-')
    .map(part => (part ? part[0].toUpperCase() + part.slice(1) : ''))
    .join('');
}

const LUCIDE_ICON_ALLOWLIST: Record<string, LucideIcon> = {
  Bot,
  Brush,
  Code,
  Database,
  Feather,
  FileText,
  Globe,
  Image,
  LayoutDashboard,
  MessageSquare,
  Monitor,
  Palette,
  Search,
  Settings,
  Shield,
  Smartphone,
  Sparkles,
};

function resolveLucideIcon(name: string | undefined): LucideIcon | null {
  if (!name) return null;
  const pascal = kebabToPascal(name);
  return LUCIDE_ICON_ALLOWLIST[pascal] ?? LUCIDE_ICON_ALLOWLIST[name] ?? null;
}

function clampNumber(raw: string, min?: number | string, max?: number | string): string {
  if (raw.trim() === '') return '';
  const n = Number(raw);
  if (!Number.isFinite(n)) return '';
  const minN = min !== undefined ? Number(min) : undefined;
  const maxN = max !== undefined ? Number(max) : undefined;
  let clamped = n;
  if (minN !== undefined && Number.isFinite(minN) && clamped < minN) clamped = minN;
  if (maxN !== undefined && Number.isFinite(maxN) && clamped > maxN) clamped = maxN;
  return String(clamped);
}

function buildInitialAnswers(
  form: QuestionForm,
  submitted?: Record<string, string | string[]> | null,
): Record<string, string | string[]> {
  const out: Record<string, string | string[]> = {};
  for (const q of form.questions ?? []) {
    if (submitted && submitted[q.id] !== undefined) {
      const submittedValue = submitted[q.id];
      out[q.id] = submittedValue;
    } else if (q.default !== undefined) {
      out[q.id] = Array.isArray(q.default) ? [...q.default] : q.default;
    } else if (q.type === 'checkbox' || (q.type === 'option-cards' && q.multiple)) {
      out[q.id] = [];
    } else {
      out[q.id] = '';
    }
  }
  return out;
}

function RadioField({ options, value, locked, onChange }: {
  options: string[];
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => (
        <button
          key={opt}
          type="button"
          disabled={locked}
          onClick={() => !locked && onChange(opt)}
          className={cn(
            'px-3 py-1.5 rounded-full text-sm border transition-colors',
            value === opt
              ? 'bg-primary text-primary-foreground border-primary'
              : 'bg-background border-border hover:border-primary/60',
            locked && 'opacity-60 cursor-default',
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function CheckboxField({ options, value, locked, onChange }: {
  options: string[];
  value: string[];
  locked: boolean;
  onChange: (v: string[]) => void;
}) {
  const toggle = (opt: string) => {
    if (locked) return;
    onChange(
      value.includes(opt)
        ? value.filter(v => v !== opt)
        : [...value, opt],
    );
  };
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => (
        <button
          key={opt}
          type="button"
          disabled={locked}
          onClick={() => toggle(opt)}
          className={cn(
            'px-3 py-1.5 rounded-full text-sm border transition-colors',
            value.includes(opt)
              ? 'bg-primary text-primary-foreground border-primary'
              : 'bg-background border-border hover:border-primary/60',
            locked && 'opacity-60 cursor-default',
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function NumberField({ question, value, locked, onChange }: {
  question: FormQuestion;
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="number"
        inputMode="numeric"
        value={value}
        min={question.min}
        max={question.max}
        step={question.step ?? 1}
        placeholder={question.placeholder ?? ''}
        disabled={locked}
        onChange={e => onChange(e.target.value)}
        onBlur={e => onChange(clampNumber(e.target.value, question.min, question.max))}
        className="max-w-32"
      />
      {question.unit && (
        <span className="text-sm text-muted-foreground">{question.unit}</span>
      )}
    </div>
  );
}

function DateField({ question, value, locked, onChange }: {
  question: FormQuestion;
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
}) {
  const isDatetime = question.mode === 'datetime';
  const inputType = isDatetime ? 'datetime-local' : 'date';
  return (
    <Input
      type={inputType}
      value={value}
      min={typeof question.min === 'string' ? question.min : undefined}
      max={typeof question.max === 'string' ? question.max : undefined}
      disabled={locked}
      onChange={e => onChange(e.target.value)}
      className={cn('w-fit min-w-0', isDatetime ? 'pr-3' : 'pr-2')}
    />
  );
}

function YesNoField({ question, value, locked, onChange, t }: {
  question: FormQuestion;
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
  t: (key: string) => string;
}) {
  const yesLabel = question.yes_label ?? t('aiChat.questionForm.yes');
  const noLabel = question.no_label ?? t('aiChat.questionForm.no');
  const labels = [yesLabel, noLabel];
  return (
    <div className="flex gap-3">
      {labels.map(label => (
        <button
          key={label}
          type="button"
          disabled={locked}
          onClick={() => !locked && onChange(label)}
          className={cn(
            'px-5 py-1.5 rounded-full text-sm border transition-colors min-w-20',
            value === label
              ? 'bg-primary text-primary-foreground border-primary'
              : 'bg-background border-border hover:border-primary/60',
            locked && 'opacity-60 cursor-default',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function OptionCardsField({ question, value, locked, onChange }: {
  question: FormQuestion;
  value: string | string[];
  locked: boolean;
  onChange: (v: string | string[]) => void;
}) {
  const multiple = !!question.multiple;
  const selected = multiple
    ? (Array.isArray(value) ? value : [])
    : (typeof value === 'string' ? value : '');

  const isSelected = (card: OptionCard) =>
    multiple ? (selected as string[]).includes(card.label) : selected === card.label;

  const handleClick = (card: OptionCard) => {
    if (locked) return;
    if (multiple) {
      const current = selected as string[];
      onChange(
        current.includes(card.label)
          ? current.filter(v => v !== card.label)
          : [...current, card.label],
      );
    } else {
      onChange(card.label);
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {question.cards?.map(card => {
        const Icon = resolveLucideIcon(card.icon);
        const showPalette = !Icon && Array.isArray(card.palette) && card.palette.length > 0;
        const active = isSelected(card);
        return (
          <button
            key={card.id}
            type="button"
            disabled={locked}
            onClick={() => handleClick(card)}
            className={cn(
              'relative flex flex-col items-start text-left rounded-lg border p-3 transition-colors',
              active
                ? 'border-primary bg-primary/5 ring-1 ring-primary'
                : 'border-border hover:border-primary/50',
              locked && 'opacity-60 cursor-default',
            )}
          >
            {multiple && active && (
              <span className="absolute top-2 right-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground">
                <Check className="w-3 h-3" />
              </span>
            )}
            {Icon && (
              <Icon className="w-5 h-5 mb-2 text-primary shrink-0" aria-hidden />
            )}
            {showPalette && (
              <div className="flex gap-1.5 mb-2 shrink-0">
                {card.palette!.map((hex, i) => (
                  <span
                    key={i}
                    className="w-5 h-5 rounded-full border border-black/10 shrink-0"
                    style={{ backgroundColor: hex }}
                  />
                ))}
              </div>
            )}
            <div
              className="text-sm font-semibold mb-0.5"
              style={card.displayFont ? { fontFamily: card.displayFont } : undefined}
            >
              {card.label}
            </div>
            {(card.description || card.mood) && (
              <div
                className="text-xs text-muted-foreground leading-relaxed"
                style={card.bodyFont ? { fontFamily: card.bodyFont } : undefined}
              >
                {card.description ?? card.mood}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}

function ColorField({ question, value, locked, onChange, t }: {
  question: FormQuestion;
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
  t: (key: string) => string;
}) {
  const allowCustom = question.allow_custom !== false;
  const swatches = question.swatches ?? [];
  const normalized = value ? normalizeHex(value) : '';
  return (
    <div className="flex flex-wrap items-center gap-3">
      {swatches.length > 0 && (
        <div className="flex flex-wrap gap-2" aria-label={t('aiChat.questionForm.selectColor')}>
          {swatches.map(hex => {
            const swatchHex = normalizeHex(hex);
            if (!swatchHex) return null;
            const active = normalized === swatchHex;
            return (
              <button
                key={swatchHex}
                type="button"
                disabled={locked}
                onClick={() => !locked && onChange(swatchHex)}
                aria-label={swatchHex}
                className={cn(
                  'w-6 h-6 rounded-full border border-black/10 transition-shadow',
                  active && 'ring-2 ring-primary ring-offset-1',
                  locked && 'opacity-60 cursor-default',
                )}
                style={{ backgroundColor: swatchHex }}
              />
            );
          })}
        </div>
      )}
      {allowCustom && (
        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="color"
            value={normalized || '#000000'}
            disabled={locked}
            onChange={e => onChange(normalizeHex(e.target.value))}
            className="w-8 h-8 rounded border border-border bg-transparent p-0 cursor-pointer disabled:cursor-default"
          />
          <span>{t('aiChat.questionForm.customColor')}</span>
        </label>
      )}
      {normalized && (
        <span className="text-xs font-mono text-muted-foreground">{normalized}</span>
      )}
    </div>
  );
}

export const QuestionFormView: React.FC<QuestionFormViewProps> = ({
  form,
  interactive,
  submittedAnswers,
  isSubmitting = false,
  errorKey = null,
  onSubmit,
}) => {
  const { t } = useI18n();
  const locked = !interactive || submittedAnswers != null || isSubmitting;
  const hasSubmittedAnswers = submittedAnswers != null;

  const [answers, setAnswers] = useState<Record<string, string | string[]>>(() =>
    buildInitialAnswers(form, submittedAnswers),
  );
  const isLocked = locked;
  const showAnswered = hasSubmittedAnswers;

  const visibleQuestions = useMemo(
    () => computeVisibleQuestions(form, answers),
    [form, answers],
  );

  const isReady = useMemo(() => {
    return visibleQuestions.every(q => {
      if (!q.required) return true;
      const v = answers[q.id];
      if (Array.isArray(v)) return v.length > 0;
      return typeof v === 'string' && v.trim().length > 0;
    });
  }, [visibleQuestions, answers]);

  const update = (id: string, value: string | string[]) => {
    if (isLocked) return;
    setAnswers(prev => cleanupAnswers(form, { ...prev, [id]: value }));
  };

  const handleSubmit = () => {
    if (isLocked || !isReady) return;
    const normalized: Record<string, string | string[]> = { ...answers };
    for (const q of form.questions ?? []) {
      if (q.type === 'number') {
        const v = normalized[q.id];
        if (typeof v === 'string' && v.trim() !== '') {
          normalized[q.id] = clampNumber(v, q.min, q.max);
        }
      }
    }
    const formatted = formatFormAnswers(form, normalized);
    onSubmit?.(formatted, normalized);
  };

  const renderField = (q: FormQuestion) => {
    const value = answers[q.id];
    const options = resolveQuestionOptions(q, form, answers);
    if (q.type === 'radio') {
      return (
        <RadioField
          options={options}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
        />
      );
    }
    if (q.type === 'checkbox') {
      return (
        <CheckboxField
          options={options}
          value={Array.isArray(value) ? value : []}
          locked={isLocked}
          onChange={v => update(q.id, v)}
        />
      );
    }
    if (q.type === 'select') {
      return (
        <Select
          value={typeof value === 'string' ? value : ''}
          onValueChange={v => !isLocked && update(q.id, v)}
          disabled={isLocked}
        >
          <SelectTrigger className="w-full max-w-xs">
            <SelectValue placeholder={q.placeholder ?? ''} />
          </SelectTrigger>
          <SelectContent>
            {options.map(opt => (
              <SelectItem key={opt} value={opt}>{opt}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }
    if (q.type === 'text') {
      return (
        <Input
          value={typeof value === 'string' ? value : ''}
          onChange={e => update(q.id, e.target.value)}
          placeholder={q.placeholder ?? ''}
          disabled={isLocked}
          className="max-w-xs"
        />
      );
    }
    if (q.type === 'textarea') {
      return (
        <Textarea
          value={typeof value === 'string' ? value : ''}
          onChange={e => update(q.id, e.target.value)}
          placeholder={q.placeholder ?? ''}
          disabled={isLocked}
          rows={3}
        />
      );
    }
    if (q.type === 'number') {
      return (
        <NumberField
          question={q}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
        />
      );
    }
    if (q.type === 'date') {
      return (
        <DateField
          question={q}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
        />
      );
    }
    if (q.type === 'yes-no') {
      return (
        <YesNoField
          question={q}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
          t={t}
        />
      );
    }
    if (q.type === 'option-cards') {
      return (
        <OptionCardsField
          question={q}
          value={q.multiple ? (Array.isArray(value) ? value : []) : (typeof value === 'string' ? value : '')}
          locked={isLocked}
          onChange={v => update(q.id, v)}
        />
      );
    }
    if (q.type === 'color') {
      return (
        <ColorField
          question={q}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
          t={t}
        />
      );
    }
    return null;
  };

  return (
    <div className={cn(
      'rounded-lg border bg-muted/30 p-4 space-y-4',
      isLocked && 'opacity-80',
    )}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center">?</span>
          <span className="font-medium text-sm">{form.title}</span>
        </div>
        {showAnswered && (
          <span className="text-xs bg-muted border border-border rounded-full px-2 py-0.5 text-muted-foreground flex-shrink-0">
            {t('aiChat.questionForm.answered')}
          </span>
        )}
      </div>
      {errorKey && !hasSubmittedAnswers && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {t(errorKey)}
        </div>
      )}

      <div className="space-y-4">
        {visibleQuestions.map(q => (
          <div key={q.id} className="space-y-2">
            <label className="flex items-center gap-1 text-sm font-medium">
              {q.label}
              {q.required && (
                <span className="text-destructive text-xs" aria-label={t('aiChat.questionForm.required')}>
                  *
                </span>
              )}
            </label>
            {renderField(q)}
          </div>
        ))}
      </div>

      {!isLocked && (
        <Button
          size="sm"
          disabled={!isReady || isSubmitting}
          onClick={handleSubmit}
        >
          {t(isSubmitting ? 'aiChat.questionForm.submitting' : 'aiChat.questionForm.submit')}
        </Button>
      )}
    </div>
  );
};
