// @vitest-environment jsdom
import { render, screen, fireEvent } from '@/__tests__/utils/render';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import { QuestionFormView } from './QuestionFormView';
import { WORKSPACE_CHAT_SEND_DRAFT_EVENT } from './chatEvents';
import type { QuestionForm } from './question-form';

const baseForm: QuestionForm = {
  id: 'discovery',
  title: 'Tell me about your project',
  questions: [
    { id: 'type', label: 'Page type', type: 'radio', options: ['Landing', 'Dashboard'], required: true },
    { id: 'desc', label: 'Description', type: 'textarea' },
  ],
};

describe('QuestionFormView', () => {
  describe('radio field', () => {
    it('renders options as chips', () => {
      render(<QuestionFormView form={baseForm} interactive />);
      expect(screen.getByText('Landing')).toBeInTheDocument();
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    it('selecting a chip updates state', () => {
      render(<QuestionFormView form={baseForm} interactive />);
      fireEvent.click(screen.getByText('Landing'));
      expect(screen.getByText('Landing').closest('button')).toHaveClass('bg-primary');
    });
  });

  describe('checkbox field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'feat', label: 'Features', type: 'checkbox', options: ['Auth', 'Search', 'Export'] }],
    };

    it('renders checkbox options as chips', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('Auth')).toBeInTheDocument();
    });

    it('allows multiple selections', () => {
      render(<QuestionFormView form={form} interactive />);
      fireEvent.click(screen.getByText('Auth'));
      fireEvent.click(screen.getByText('Search'));
      expect(screen.getByText('Auth').closest('button')).toHaveClass('bg-primary');
      expect(screen.getByText('Search').closest('button')).toHaveClass('bg-primary');
    });

    it('restores submitted checkbox answers from formatted history text', () => {
      render(
        <QuestionFormView
          form={form}
          interactive={false}
          submittedAnswers={{ Features: 'Auth, Export' }}
        />,
      );

      expect(screen.getByText('Auth').closest('button')).toHaveClass('bg-primary');
      expect(screen.getByText('Search').closest('button')).not.toHaveClass('bg-primary');
      expect(screen.getByText('Export').closest('button')).toHaveClass('bg-primary');
    });
  });

  describe('select field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'style', label: 'Style', type: 'select', options: ['Minimal', 'Bold'] }],
    };

    it('renders a select trigger', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });
  });

  describe('text field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'name', label: 'Name', type: 'text', placeholder: 'Enter name' }],
    };

    it('renders a text input', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByPlaceholderText('Enter name')).toBeInTheDocument();
    });
  });

  describe('textarea field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'desc', label: 'Description', type: 'textarea', placeholder: 'Describe...' }],
    };

    it('renders a textarea', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByPlaceholderText('Describe...')).toBeInTheDocument();
    });
  });

  describe('direction-cards field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{
        id: 'dir', label: 'Direction', type: 'direction-cards',
        cards: [
          { id: 'minimal', label: 'Minimal — Clean', mood: 'Lots of white space.', palette: ['#FFF', '#000'], displayFont: 'Inter', bodyFont: 'Inter' },
          { id: 'bold', label: 'Bold — Expressive', mood: 'Strong colours.', palette: ['#F00', '#000'], displayFont: 'Bebas', bodyFont: 'Inter' },
        ],
      }],
    };

    it('renders direction cards', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('Minimal — Clean')).toBeInTheDocument();
      expect(screen.getByText('Bold — Expressive')).toBeInTheDocument();
    });

    it('selecting a card activates it', () => {
      render(<QuestionFormView form={form} interactive />);
      const card = screen.getByText('Minimal — Clean').closest('button');
      fireEvent.click(card!);
      expect(card).toHaveClass('border-primary');
    });
  });

  describe('required validation', () => {
    it('submit button is disabled when required field is empty', () => {
      render(<QuestionFormView form={baseForm} interactive />);
      const submit = screen.getByRole('button', { name: /submit/i });
      expect(submit).toBeDisabled();
    });

    it('submit button enables when all required fields are filled', () => {
      render(<QuestionFormView form={baseForm} interactive />);
      fireEvent.click(screen.getByText('Landing'));
      const submit = screen.getByRole('button', { name: /submit/i });
      expect(submit).not.toBeDisabled();
    });
  });

  describe('submit event dispatch', () => {
    it('dispatches WORKSPACE_CHAT_SEND_DRAFT_EVENT on submit', () => {
      const handler = vi.fn();
      window.addEventListener(WORKSPACE_CHAT_SEND_DRAFT_EVENT, handler);

      render(<QuestionFormView form={baseForm} interactive />);
      fireEvent.click(screen.getByText('Landing'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));

      expect(handler).toHaveBeenCalledTimes(1);
      window.removeEventListener(WORKSPACE_CHAT_SEND_DRAFT_EVENT, handler);
    });

    it('calls onSubmit callback with formatted text', () => {
      const onSubmit = vi.fn();
      render(<QuestionFormView form={baseForm} interactive onSubmit={onSubmit} />);
      fireEvent.click(screen.getByText('Dashboard'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      expect(onSubmit).toHaveBeenCalledTimes(1);
      const [formatted] = onSubmit.mock.calls[0];
      expect(formatted).toContain('[form answers — discovery]');
      expect(formatted).toContain('Dashboard');
    });
  });

  describe('locked state', () => {
    it('does not render answered pill for an unanswered locked form', () => {
      render(<QuestionFormView form={baseForm} interactive={false} />);
      expect(screen.queryByText('workspace.chat.questionForm.answered')).toBeNull();
    });

    it('does not render submit button when locked', () => {
      render(<QuestionFormView form={baseForm} interactive={false} />);
      expect(screen.queryByRole('button', { name: /submit/i })).toBeNull();
    });

    it('locks immediately after submit without waiting for re-render', () => {
      render(<QuestionFormView form={baseForm} interactive />);
      fireEvent.click(screen.getByText('Landing'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      expect(screen.getByText('workspace.chat.questionForm.answered')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /submit/i })).toBeNull();
    });
  });

  describe('submittedAnswers pre-fill', () => {
    it('renders with submitted answers in locked state', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [{ id: 'type', label: 'Page type', type: 'radio', options: ['Landing', 'Dashboard'] }],
      };
      render(
        <QuestionFormView
          form={form}
          interactive={false}
          submittedAnswers={{ 'Page type': 'Landing' }}
        />,
      );
      expect(screen.getByText('workspace.chat.questionForm.answered')).toBeInTheDocument();
    });
  });
});
