/**
 * AskUserQuestionWidget - compact user question widget.
 *
 * Displays Claude Code AskUserQuestion tool calls with single and multi-select options.
 */

import React, { useState, useMemo } from 'react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { RadioGroup, RadioGroupItem } from '@/shared/components/ui/radio-group';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Label } from '@/shared/components/ui/label';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { X, Check } from 'lucide-react';
import { WidgetProps } from './types';

// ============================================================================
// Types
// ============================================================================

export interface AskUserQuestionOption {
  label: string;
  description: string;
}

export interface AskUserQuestion {
  header: string;
  question: string;
  options: AskUserQuestionOption[];
  multiSelect: boolean;
}

export interface AskUserQuestionInput {
  questions: AskUserQuestion[];
}

export interface AskUserQuestionWidgetProps extends WidgetProps {
  /** Submit callback. */
  onSubmit?: (answers: Record<string, string | string[]>) => void;
  /** Cancel callback. */
  onCancel?: () => void;
  /** Whether action buttons are visible. */
  showActions?: boolean;
  /** Whether the question has been submitted. */
  isSubmitted?: boolean;
  /** Submitted answers used for completed state display. */
  submittedAnswers?: Record<string, string | string[]>;
}

export const AskUserQuestionWidget: React.FC<AskUserQuestionWidgetProps> = ({
  input,
  output,
  status,
  isExpanded,
  onSubmit,
  onCancel,
  showActions = true,
  isSubmitted = false,
  submittedAnswers,
}) => {
  const { t } = useI18n();

  // Parse input questions.
  const questions = useMemo(() => {
    const rawQuestions = input?.questions as AskUserQuestion[] | undefined;
    return rawQuestions || [];
  }, [input]);

  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [otherInputs, setOtherInputs] = useState<Record<string, string>>({});
  const [otherSelected, setOtherSelected] = useState<Record<string, boolean>>({});

  const isCompleted = status === 'completed' || isSubmitted;
  const isPending = status === 'pending' || status === 'in_progress';

  const displayAnswers = isCompleted && submittedAnswers ? submittedAnswers : answers;

  // Derive Other option state from submitted answers that are not predefined options.
  const derivedOther = useMemo(() => {
    if (!isCompleted || !submittedAnswers) return null;
    const selected: Record<string, boolean> = {};
    const inputs: Record<string, string> = {};
    questions.forEach((question, index) => {
      const key = `q${index}`;
      const answer = submittedAnswers[key];
      if (!answer) return;
      const optionLabels = question.options.map(o => o.label);
      if (question.multiSelect) {
        const arr = Array.isArray(answer) ? answer : [answer];
        const otherVal = arr.find(a => !optionLabels.includes(a));
        if (otherVal) {
          selected[key] = true;
          inputs[key] = otherVal;
        }
      } else {
        if (!optionLabels.includes(answer as string)) {
          selected[key] = true;
          inputs[key] = answer as string;
        }
      }
    });
    return { selected, inputs };
  }, [isCompleted, submittedAnswers, questions]);

  const handleSingleSelect = (questionIndex: number, value: string, isOther: boolean = false) => {
    const key = `q${questionIndex}`;
    setOtherSelected(prev => ({ ...prev, [key]: isOther }));

    if (isOther) {
      setAnswers(prev => ({ ...prev, [key]: otherInputs[key] || '' }));
    } else {
      setAnswers(prev => ({ ...prev, [key]: value }));
    }
  };

  const handleMultiSelect = (questionIndex: number, value: string, checked: boolean, isOther: boolean = false) => {
    const key = `q${questionIndex}`;
    const currentValues = (answers[key] as string[]) || [];

    if (isOther) {
      setOtherSelected(prev => ({ ...prev, [key]: checked }));
      if (checked) {
        const otherValue = otherInputs[key] || '';
        setAnswers(prev => ({
          ...prev,
          [key]: [...currentValues.filter(v => !v.startsWith('__other__:')), `__other__:${otherValue}`],
        }));
      } else {
        setAnswers(prev => ({
          ...prev,
          [key]: currentValues.filter(v => !v.startsWith('__other__:')),
        }));
      }
    } else {
      if (checked) {
        setAnswers(prev => ({ ...prev, [key]: [...currentValues, value] }));
      } else {
        setAnswers(prev => ({
          ...prev,
          [key]: currentValues.filter(v => v !== value),
        }));
      }
    }
  };

  const handleOtherInputChange = (questionIndex: number, value: string) => {
    const key = `q${questionIndex}`;
    setOtherInputs(prev => ({ ...prev, [key]: value }));

    // Keep answers in sync while Other is selected.
    if (otherSelected[key]) {
      const question = questions[questionIndex];
      if (question.multiSelect) {
        const currentValues = (answers[key] as string[]) || [];
        setAnswers(prev => ({
          ...prev,
          [key]: [...currentValues.filter(v => !v.startsWith('__other__:')), `__other__:${value}`],
        }));
      } else {
        setAnswers(prev => ({ ...prev, [key]: value }));
      }
    }
  };

  const handleSubmit = () => {
    if (onSubmit) {
      // Normalize Other answers before submitting.
      const cleanedAnswers: Record<string, string | string[]> = {};
      Object.entries(answers).forEach(([key, value]) => {
        if (Array.isArray(value)) {
          cleanedAnswers[key] = value.map(v =>
            v.startsWith('__other__:') ? v.replace('__other__:', '') : v
          );
        } else {
          cleanedAnswers[key] = value;
        }
      });
      onSubmit(cleanedAnswers);
    }
  };

  const canSubmit = questions.every((_, index) => {
    const key = `q${index}`;
    const answer = answers[key];
    if (Array.isArray(answer)) {
      return answer.length > 0;
    }
    return answer && answer.length > 0;
  });

  if (questions.length === 0) {
    return (
      <div className="px-2 py-1.5 text-xs text-muted-foreground">
        {t('workspace.chat.widgets.agentTools.noQuestion')}
      </div>
    );
  }

  const renderQuestion = (question: AskUserQuestion, index: number) => {
    const key = `q${index}`;
    const currentAnswer = displayAnswers[key];
    const isOtherActive = derivedOther ? derivedOther.selected[key] : otherSelected[key];
    const otherInputValue = derivedOther ? (derivedOther.inputs[key] || '') : (otherInputs[key] || '');

    return (
      <div key={index} className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
            {question.header}
          </span>
          <div className="h-px flex-1 bg-border" />
          {onCancel && isPending && index === 0 && (
            <button
              onClick={onCancel}
              className="p-0.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        <p className="text-xs font-medium text-foreground">
          {question.question}
        </p>

        {question.multiSelect ? (
          <div className="space-y-0.5">
            {question.options.map((option, optIndex) => {
              const isSelected = Array.isArray(currentAnswer) && currentAnswer.includes(option.label);
              return (
                <div
                  key={optIndex}
                  className={cn(
                    'flex items-center gap-2 py-0.5 px-1.5 rounded cursor-pointer transition-colors',
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-950/40'
                      : 'hover:bg-muted/50',
                    isCompleted && 'cursor-default'
                  )}
                  onClick={() => !isCompleted && handleMultiSelect(index, option.label, !isSelected)}
                >
                  <Checkbox
                    id={`${key}-option-${optIndex}`}
                    checked={isSelected}
                    disabled={isCompleted}
                    onCheckedChange={(checked) => handleMultiSelect(index, option.label, !!checked)}
                    className="h-3.5 w-3.5"
                  />
                  <Label
                    htmlFor={`${key}-option-${optIndex}`}
                    className="text-xs font-medium text-foreground cursor-pointer flex-shrink-0"
                  >
                    {option.label}
                  </Label>
                  <span className="text-[10px] text-muted-foreground truncate">
                    {option.description}
                  </span>
                </div>
              );
            })}

            <div
              className={cn(
                'flex items-center gap-2 py-0.5 px-1.5 rounded transition-colors',
                isOtherActive
                  ? 'bg-blue-50 dark:bg-blue-950/40'
                  : 'hover:bg-muted/50',
                isCompleted && 'cursor-default'
              )}
            >
              <Checkbox
                id={`${key}-other`}
                checked={isOtherActive}
                disabled={isCompleted}
                onCheckedChange={(checked) => handleMultiSelect(index, '', !!checked, true)}
                className="h-3.5 w-3.5"
              />
              <Label
                htmlFor={`${key}-other`}
                className="text-xs font-medium text-foreground cursor-pointer"
              >
                Other
              </Label>
              {isOtherActive && (
                <Input
                  placeholder={t('workspace.chat.widgets.agentTools.answerPlaceholder')}
                  value={otherInputValue}
                  onChange={(e) => handleOtherInputChange(index, e.target.value)}
                  disabled={isCompleted}
                  className="h-6 text-xs flex-1 ml-1"
                  onClick={(e) => e.stopPropagation()}
                />
              )}
            </div>
          </div>
        ) : (
          <RadioGroup
            value={isOtherActive ? '__other__' : (currentAnswer as string) || ''}
            onValueChange={(value) => {
              if (value === '__other__') {
                handleSingleSelect(index, '', true);
              } else {
                handleSingleSelect(index, value, false);
              }
            }}
            disabled={isCompleted}
            className="space-y-0.5"
          >
            {question.options.map((option, optIndex) => {
              const isSelected = currentAnswer === option.label && !isOtherActive;
              return (
                <div
                  key={optIndex}
                  className={cn(
                    'flex items-center gap-2 py-0.5 px-1.5 rounded cursor-pointer transition-colors',
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-950/40'
                      : 'hover:bg-muted/50',
                    isCompleted && 'cursor-default'
                  )}
                  onClick={() => !isCompleted && handleSingleSelect(index, option.label, false)}
                >
                  <RadioGroupItem
                    value={option.label}
                    id={`${key}-option-${optIndex}`}
                    disabled={isCompleted}
                    className="h-3.5 w-3.5"
                  />
                  <Label
                    htmlFor={`${key}-option-${optIndex}`}
                    className="text-xs font-medium text-foreground cursor-pointer flex-shrink-0"
                  >
                    {option.label}
                  </Label>
                  <span className="text-[10px] text-muted-foreground truncate">
                    {option.description}
                  </span>
                </div>
              );
            })}

            <div
              className={cn(
                'flex items-center gap-2 py-0.5 px-1.5 rounded transition-colors',
                isOtherActive
                  ? 'bg-blue-50 dark:bg-blue-950/40'
                  : 'hover:bg-muted/50',
                isCompleted && 'cursor-default'
              )}
              onClick={() => !isCompleted && handleSingleSelect(index, '', true)}
            >
              <RadioGroupItem
                value="__other__"
                id={`${key}-other`}
                disabled={isCompleted}
                className="h-3.5 w-3.5"
              />
              <Label
                htmlFor={`${key}-other`}
                className="text-xs font-medium text-foreground cursor-pointer"
              >
                Other
              </Label>
              {isOtherActive && (
                <Input
                  placeholder={t('workspace.chat.widgets.agentTools.answerPlaceholder')}
                  value={otherInputValue}
                  onChange={(e) => handleOtherInputChange(index, e.target.value)}
                  disabled={isCompleted}
                  className="h-6 text-xs flex-1 ml-1"
                  onClick={(e) => e.stopPropagation()}
                />
              )}
            </div>
          </RadioGroup>
        )}
      </div>
    );
  };

  return (
    <div className="px-2 py-2 space-y-3">
      {questions.map((question, index) => renderQuestion(question, index))}

      {showActions && isPending && onSubmit && (
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          size="sm"
          className={cn(
            'w-full h-7 text-xs font-medium',
            canSubmit
              ? 'bg-blue-600 hover:bg-blue-700 text-white'
              : 'bg-muted text-muted-foreground cursor-not-allowed'
          )}
        >
          <span className="inline-flex items-center justify-center h-4 w-4 rounded bg-white/20 text-[10px] font-bold mr-1.5">
            {questions.length}
          </span>
          {t('workspace.chat.widgets.agentTools.submitAnswers')}
        </Button>
      )}

      {isCompleted && (
        <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400 pt-1 border-t border-border">
          <Check className="h-3 w-3" />
          <span>{t('workspace.chat.widgets.agentTools.answerSubmitted')}</span>
        </div>
      )}
    </div>
  );
};

export default AskUserQuestionWidget;
