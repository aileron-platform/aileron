import { createContext } from 'react';

interface QuestionAnswerContextValue {
  canAnswer: boolean;
  answerStatus: (
    messageId: string,
  ) => {
    isPending: boolean;
    errorKey: string | null;
  };
  answerQuestion:
    | ((
        messageId: string,
        answers: Record<string, string | string[]>,
        text: string,
      ) => void)
    | null;
}

export const QuestionAnswerContext = createContext<QuestionAnswerContextValue>({
  canAnswer: false,
  answerStatus: () => ({ isPending: false, errorKey: null }),
  answerQuestion: null,
});
