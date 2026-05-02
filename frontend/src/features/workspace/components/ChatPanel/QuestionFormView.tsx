import React, { useState, useMemo } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { dispatchSendDraftEvent } from './chatEvents';
import { formatFormAnswers } from './question-form';
import type { QuestionForm, FormQuestion, DirectionCard } from './question-form';

interface QuestionFormViewProps {
  form: QuestionForm;
  interactive: boolean;
  submittedAnswers?: Record<string, string | string[]> | null;
  onSubmit?: (formattedText: string, answers: Record<string, string | string[]>) => void;
}

function buildInitialAnswers(
  form: QuestionForm,
  submitted?: Record<string, string | string[]> | null,
): Record<string, string | string[]> {
  const out: Record<string, string | string[]> = {};
  for (const q of form.questions) {
    if (submitted && submitted[q.label] !== undefined) {
      const submittedValue = submitted[q.label];
      out[q.id] = q.type === 'checkbox' && typeof submittedValue === 'string'
        ? submittedValue.split(',').map(v => v.trim()).filter(Boolean)
        : submittedValue;
    } else if (q.type === 'checkbox') {
      out[q.id] = [];
    } else {
      out[q.id] = '';
    }
  }
  return out;
}

function RadioField({ question, value, locked, onChange }: {
  question: FormQuestion;
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {question.options?.map(opt => (
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

function CheckboxField({ question, value, locked, onChange }: {
  question: FormQuestion;
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
      {question.options?.map(opt => (
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

function DirectionCardsField({ question, value, locked, onChange }: {
  question: FormQuestion;
  value: string;
  locked: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {question.cards?.map((card: DirectionCard) => (
        <button
          key={card.id}
          type="button"
          disabled={locked}
          onClick={() => !locked && onChange(card.id)}
          className={cn(
            'text-left rounded-lg border p-3 transition-colors',
            value === card.id
              ? 'border-primary bg-primary/5 ring-1 ring-primary'
              : 'border-border hover:border-primary/50',
            locked && 'opacity-60 cursor-default',
          )}
        >
          <div className="flex gap-1.5 mb-2">
            {card.palette.map((hex, i) => (
              <span
                key={i}
                className="w-5 h-5 rounded-full border border-black/10 flex-shrink-0"
                style={{ backgroundColor: hex }}
              />
            ))}
          </div>
          <div className="text-sm font-semibold mb-0.5" style={{ fontFamily: card.displayFont }}>
            {card.label}
          </div>
          <div className="text-xs text-muted-foreground leading-relaxed">{card.mood}</div>
        </button>
      ))}
    </div>
  );
}

export const QuestionFormView: React.FC<QuestionFormViewProps> = ({
  form,
  interactive,
  submittedAnswers,
  onSubmit,
}) => {
  const { t } = useI18n();
  const locked = !interactive || submittedAnswers !== undefined;
  const hasSubmittedAnswers = submittedAnswers != null;

  const [answers, setAnswers] = useState<Record<string, string | string[]>>(() =>
    buildInitialAnswers(form, submittedAnswers),
  );
  const [locallySubmitted, setLocallySubmitted] = useState(false);
  const isLocked = locked || locallySubmitted;
  const showAnswered = hasSubmittedAnswers || locallySubmitted;

  const isReady = useMemo(() => {
    return form.questions.every(q => {
      if (!q.required) return true;
      const v = answers[q.id];
      if (Array.isArray(v)) return v.length > 0;
      return typeof v === 'string' && v.trim().length > 0;
    });
  }, [form.questions, answers]);

  const update = (id: string, value: string | string[]) => {
    if (isLocked) return;
    setAnswers(prev => ({ ...prev, [id]: value }));
  };

  const handleSubmit = () => {
    if (isLocked || !isReady) return;
    const formatted = formatFormAnswers(form, answers);
    setLocallySubmitted(true);
    onSubmit?.(formatted, answers);
    dispatchSendDraftEvent({ content: formatted });
  };

  const renderField = (q: FormQuestion) => {
    const value = answers[q.id];
    if (q.type === 'radio') {
      return (
        <RadioField
          question={q}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
        />
      );
    }
    if (q.type === 'checkbox') {
      return (
        <CheckboxField
          question={q}
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
            {q.options?.map(opt => (
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
    if (q.type === 'direction-cards') {
      return (
        <DirectionCardsField
          question={q}
          value={typeof value === 'string' ? value : ''}
          locked={isLocked}
          onChange={v => update(q.id, v)}
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
            {t('workspace.chat.questionForm.answered')}
          </span>
        )}
      </div>

      <div className="space-y-4">
        {form.questions.map(q => (
          <div key={q.id} className="space-y-2">
            <label className="flex items-center gap-1 text-sm font-medium">
              {q.label}
              {q.required && (
                <span className="text-destructive text-xs" aria-label={t('workspace.chat.questionForm.required')}>
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
          disabled={!isReady}
          onClick={handleSubmit}
        >
          {t('workspace.chat.questionForm.submit')}
        </Button>
      )}
    </div>
  );
};

export default QuestionFormView;
