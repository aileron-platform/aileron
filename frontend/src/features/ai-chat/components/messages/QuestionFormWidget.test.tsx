// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ContextType } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { QuestionAnswerContext } from './QuestionAnswerContext';
import { QuestionFormWidget } from './QuestionFormWidget';

type QuestionAnswerContextValue = ContextType<typeof QuestionAnswerContext>;

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const parameters = {
  id: 'color',
  title: 'Pick a color',
  questions: [
    {
      id: 'favorite',
      label: 'Favorite color',
      type: 'radio',
      options: ['red', 'blue'],
    },
  ],
};

const renderWidget = (
  props: Partial<Parameters<typeof QuestionFormWidget>[0]> = {},
  context: QuestionAnswerContextValue = {
    canAnswer: true,
    answerStatus: () => ({ isPending: false, errorKey: null }),
    answerQuestion: vi.fn(),
  },
) => {
  render(
    <QuestionAnswerContext.Provider value={context}>
      <QuestionFormWidget
        id="42"
        name="mcp__aileron__ask_user_question"
        parameters={parameters}
        status="completed"
        result={{
          messageId: 'result-1',
          isError: false,
          preview: 'Question form delivered to the user.',
          byteLength: 36,
          lineCount: 1,
          truncated: false,
          mediaType: 'text/plain',
        }}
        {...props}
      />
    </QuestionAnswerContext.Provider>,
  );
  return context;
};

describe('QuestionFormWidget', () => {
  it('renders the form title and options verbatim', () => {
    renderWidget();
    expect(screen.getByText('Pick a color')).toBeInTheDocument();
    expect(screen.getByText('red')).toBeInTheDocument();
  });

  it('submits answers through the context with the tool call message id', () => {
    const context = renderWidget();
    fireEvent.click(screen.getByText('red'));
    fireEvent.click(screen.getByText('aiChat.questionForm.submit'));
    expect(context.answerQuestion).toHaveBeenCalledWith(
      '42',
      { favorite: 'red' },
      expect.stringContaining('Favorite color: red'),
    );
  });

  it('uses question ids as answer keys so duplicate labels do not collide', () => {
    const context = renderWidget({
      parameters: {
        id: 'details',
        title: 'Details',
        questions: [
          { id: 'first', label: 'Notes', type: 'text' },
          { id: 'second', label: 'Notes', type: 'text' },
        ],
      },
    });

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0]!, { target: { value: 'first answer' } });
    fireEvent.change(inputs[1]!, { target: { value: 'second answer' } });
    fireEvent.click(screen.getByText('aiChat.questionForm.submit'));

    expect(context.answerQuestion).toHaveBeenCalledWith(
      '42',
      { first: 'first answer', second: 'second answer' },
      expect.stringContaining('Notes: first answer'),
    );
  });

  it('locks the form when the result carries answers', () => {
    renderWidget({
      result: {
        messageId: 'result-1',
        isError: false,
        preview: JSON.stringify({ answers: { favorite: 'red' } }),
        byteLength: 30,
        lineCount: 1,
        truncated: false,
        mediaType: 'application/json',
      },
    });
    expect(screen.queryByText('aiChat.questionForm.submit')).not.toBeInTheDocument();
    expect(screen.getByText('aiChat.questionForm.answered')).toBeInTheDocument();
  });

  it('locks a question whose tool call failed before delivery', () => {
    renderWidget({
      result: {
        messageId: 'result-1',
        isError: true,
        preview: 'Cannot call while in plan mode.',
        byteLength: 31,
        lineCount: 1,
        truncated: false,
        mediaType: 'text/plain',
      },
    });

    expect(screen.getByText('aiChat.questionForm.expired')).toBeInTheDocument();
    expect(screen.queryByText('aiChat.questionForm.submit')).not.toBeInTheDocument();
  });

  it('is not interactive when the thread cannot accept answers', () => {
    renderWidget({}, {
      canAnswer: false,
      answerStatus: () => ({ isPending: false, errorKey: null }),
      answerQuestion: null,
    });
    expect(screen.queryByText('aiChat.questionForm.submit')).not.toBeInTheDocument();
  });

  it('shows an answer error without marking the form answered', () => {
    renderWidget({}, {
      canAnswer: true,
      answerStatus: () => ({
        isPending: false,
        errorKey: 'aiChat.questionForm.expired',
      }),
      answerQuestion: vi.fn(),
    });

    expect(screen.getByText('aiChat.questionForm.expired')).toBeInTheDocument();
    expect(screen.queryByText('aiChat.questionForm.answered')).not.toBeInTheDocument();
    expect(screen.queryByText('aiChat.questionForm.submit')).not.toBeInTheDocument();
  });

  it('renders nothing for malformed parameters', () => {
    const { container } = render(
      <QuestionAnswerContext.Provider
        value={{
          canAnswer: true,
          answerStatus: () => ({ isPending: false, errorKey: null }),
          answerQuestion: vi.fn(),
        }}
      >
        <QuestionFormWidget
          id="42"
          name="mcp__aileron__ask_user_question"
          parameters={{ nope: true }}
          status="completed"
        />
      </QuestionAnswerContext.Provider>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
