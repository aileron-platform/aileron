/**
 * AskUserQuestionWidget - 用戶問題詢問 Widget (緊湊版)
 *
 * 用於展示 Claude Code 的 AskUserQuestion 工具調用
 * 顯示問題列表，每個問題可以有多個選項
 * 支援單選和多選模式
 */

import React, { useState, useMemo } from 'react';
import { cn } from '@/shared/utils/cn';
import { RadioGroup, RadioGroupItem } from '../radio-group';
import { Checkbox } from '../checkbox';
import { Label } from '../label';
import { Button } from '../button';
import { Input } from '../input';
import { X, Check } from 'lucide-react';
import { WidgetProps } from './types';

// ============================================================================
// 類型定義
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
  /** 提交回調 */
  onSubmit?: (answers: Record<string, string | string[]>) => void;
  /** 取消回調 */
  onCancel?: () => void;
  /** 是否顯示操作按鈕 */
  showActions?: boolean;
  /** 是否已提交 */
  isSubmitted?: boolean;
  /** 已選擇的答案（用於展示已完成狀態） */
  submittedAnswers?: Record<string, string | string[]>;
}

// ============================================================================
// Widget 組件
// ============================================================================

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
  // 解析 input
  const questions = useMemo(() => {
    const rawQuestions = input?.questions as AskUserQuestion[] | undefined;
    return rawQuestions || [];
  }, [input]);

  // 每個問題的答案狀態
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  // Other 選項的自定義輸入
  const [otherInputs, setOtherInputs] = useState<Record<string, string>>({});
  // 哪些問題選擇了 Other
  const [otherSelected, setOtherSelected] = useState<Record<string, boolean>>({});

  // 判斷是否已完成
  const isCompleted = status === 'completed' || isSubmitted;
  const isPending = status === 'pending' || status === 'in_progress';

  // 獲取顯示的答案（已提交或當前選擇）
  const displayAnswers = isCompleted && submittedAnswers ? submittedAnswers : answers;

  // 從 submittedAnswers 推導 Other 狀態（答案不在預定義選項中 → Other）
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

  // 處理單選變更
  const handleSingleSelect = (questionIndex: number, value: string, isOther: boolean = false) => {
    const key = `q${questionIndex}`;
    setOtherSelected(prev => ({ ...prev, [key]: isOther }));

    if (isOther) {
      setAnswers(prev => ({ ...prev, [key]: otherInputs[key] || '' }));
    } else {
      setAnswers(prev => ({ ...prev, [key]: value }));
    }
  };

  // 處理多選變更
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

  // 處理 Other 輸入變更
  const handleOtherInputChange = (questionIndex: number, value: string) => {
    const key = `q${questionIndex}`;
    setOtherInputs(prev => ({ ...prev, [key]: value }));

    // 如果已選擇 Other，更新答案
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

  // 處理提交
  const handleSubmit = () => {
    if (onSubmit) {
      // 清理答案格式
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

  // 檢查是否可以提交
  const canSubmit = questions.every((_, index) => {
    const key = `q${index}`;
    const answer = answers[key];
    if (Array.isArray(answer)) {
      return answer.length > 0;
    }
    return answer && answer.length > 0;
  });

  // 如果沒有問題，顯示空狀態
  if (questions.length === 0) {
    return (
      <div className="px-2 py-1.5 text-xs text-muted-foreground">
        沒有問題需要回答
      </div>
    );
  }

  // 渲染單個問題
  const renderQuestion = (question: AskUserQuestion, index: number) => {
    const key = `q${index}`;
    const currentAnswer = displayAnswers[key];
    const isOtherActive = derivedOther ? derivedOther.selected[key] : otherSelected[key];
    const otherInputValue = derivedOther ? (derivedOther.inputs[key] || '') : (otherInputs[key] || '');

    return (
      <div key={index} className="space-y-1.5">
        {/* 問題 Header + 問題文字 */}
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

        {/* 選項列表 - 緊湊版 */}
        {question.multiSelect ? (
          // 多選模式
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

            {/* Other 選項 */}
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
                  placeholder="Type your answer..."
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
          // 單選模式
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

            {/* Other 選項 */}
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
                  placeholder="Type your answer..."
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
      {/* 問題列表 */}
      {questions.map((question, index) => renderQuestion(question, index))}

      {/* 操作按鈕 */}
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
          Submit answers
        </Button>
      )}

      {/* 已完成狀態顯示 - 只顯示「已提交回答」，不重複顯示問題及答案 */}
      {isCompleted && (
        <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400 pt-1 border-t border-border">
          <Check className="h-3 w-3" />
          <span>已提交回答</span>
        </div>
      )}
    </div>
  );
};

export default AskUserQuestionWidget;
