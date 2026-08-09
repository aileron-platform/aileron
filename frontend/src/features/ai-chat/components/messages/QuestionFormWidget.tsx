import { useContext } from 'react';
import { isRecord } from '@/shared/utils/typeGuards';
import { QuestionAnswerContext } from './QuestionAnswerContext';
import { QuestionFormView } from './QuestionFormView';
import { parseQuestionForm } from '../../model/questionFormModel';
import type { ToolPartProps } from './toolPartTypes';

const submittedAnswersFrom = (
  result: ToolPartProps['result'],
): Record<string, string | string[]> | null => {
  if (!isRecord(result) || typeof result.preview !== 'string') return null;
  let source: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(result.preview);
    source = isRecord(parsed) && isRecord(parsed.answers) ? parsed.answers : null;
  } catch {
    source = null;
  }
  if (source === null) return null;
  const answers: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(source)) {
    if (typeof value === 'string') {
      answers[key] = value;
    } else if (Array.isArray(value)) {
      answers[key] = value.filter((item): item is string => typeof item === 'string');
    }
  }
  return answers;
};

export const QuestionFormWidget = ({ id, parameters, result }: ToolPartProps) => {
  const { canAnswer, answerQuestion, answerStatus } = useContext(QuestionAnswerContext);
  const form = parseQuestionForm(parameters);
  if (!form) return null;

  const submittedAnswers = submittedAnswersFrom(result);
  const status = id ? answerStatus(id) : { isPending: false, errorKey: null };
  const resultFailed = isRecord(result) && result.isError === true;
  const errorKey = resultFailed ? 'aiChat.questionForm.expired' : status.errorKey;
  const expired = errorKey === 'aiChat.questionForm.expired';
  const interactive =
    submittedAnswers === null &&
    canAnswer &&
    !expired &&
    answerQuestion !== null &&
    Boolean(id);

  return (
    <QuestionFormView
      form={form}
      interactive={interactive}
      submittedAnswers={submittedAnswers}
      isSubmitting={status.isPending}
      errorKey={errorKey}
      onSubmit={(formattedText, answers) => {
        if (!id) return;
        const idAnswers: Record<string, string | string[]> = {};
        for (const question of form.questions) {
          const value = answers[question.id];
          if (value !== undefined) {
            idAnswers[question.id] = value;
          }
        }
        answerQuestion?.(id, idAnswers, formattedText);
      }}
    />
  );
};
