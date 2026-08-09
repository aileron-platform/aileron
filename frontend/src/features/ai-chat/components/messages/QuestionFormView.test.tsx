// @vitest-environment jsdom
import { render, screen, fireEvent } from '@/__tests__/utils/render';
import { describe, it, expect, vi } from 'vitest';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import { QuestionFormView } from './QuestionFormView';
import type { QuestionForm } from '../../model/questionFormModel';

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
          submittedAnswers={{ feat: ['Auth', 'Export'] }}
        />,
      );

      expect(screen.getByText('Auth').closest('button')).toHaveClass('bg-primary');
      expect(screen.getByText('Search').closest('button')).not.toHaveClass('bg-primary');
      expect(screen.getByText('Export').closest('button')).toHaveClass('bg-primary');
    });

    it('does not lock or show answered after submit until submitted answers are provided', () => {
      const onSubmit = vi.fn();
      render(<QuestionFormView form={form} interactive onSubmit={onSubmit} />);
      fireEvent.click(screen.getByText('Auth'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));

      expect(onSubmit).toHaveBeenCalledTimes(1);
      expect(screen.queryByText('aiChat.questionForm.answered')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    });

    it('shows submit errors without showing answered state', () => {
      render(
        <QuestionFormView
          form={form}
          interactive
          errorKey="aiChat.questionForm.expired"
        />,
      );

      expect(screen.getByText('aiChat.questionForm.expired')).toBeInTheDocument();
      expect(screen.queryByText('aiChat.questionForm.answered')).not.toBeInTheDocument();
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

  describe('number field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'pages', label: 'Pages', type: 'number', min: 1, max: 5, unit: 'pg', required: true }],
    };

    it('renders a number input with the unit suffix', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByRole('spinbutton')).toBeInTheDocument();
      expect(screen.getByText('pg')).toBeInTheDocument();
    });

    it('clamps the value into [min, max] on submit and does not leak the unit', () => {
      const onSubmit = vi.fn();
      render(<QuestionFormView form={form} interactive onSubmit={onSubmit} />);
      fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '9' } });
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      const [formatted] = onSubmit.mock.calls[0];
      expect(formatted).toContain('Pages: 5');
      expect(formatted).not.toContain('pg');
    });

    it('disables submit when the required number field is empty', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
    });
  });

  describe('date field', () => {
    it('renders <input type="date"> by default', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [{ id: 'when', label: 'When', type: 'date', required: true }],
      };
      const { container } = render(<QuestionFormView form={form} interactive />);
      const input = container.querySelector('input[type="date"]') as HTMLInputElement | null;
      expect(input).not.toBeNull();
    });

    it('renders <input type="datetime-local"> when mode is datetime', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [{ id: 'when', label: 'When', type: 'date', mode: 'datetime' }],
      };
      const { container } = render(<QuestionFormView form={form} interactive />);
      const input = container.querySelector('input[type="datetime-local"]') as HTMLInputElement | null;
      expect(input).not.toBeNull();
    });

    it('disables submit when required date is empty', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [{ id: 'when', label: 'When', type: 'date', required: true }],
      };
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
    });
  });

  describe('yes-no field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'allow', label: 'Allow subagent', type: 'yes-no', yes_label: 'Allow', no_label: 'Deny', required: true },
      ],
    };

    it('renders the custom labels', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('Allow')).toBeInTheDocument();
      expect(screen.getByText('Deny')).toBeInTheDocument();
    });

    it('submits the picked label verbatim', () => {
      const onSubmit = vi.fn();
      render(<QuestionFormView form={form} interactive onSubmit={onSubmit} />);
      fireEvent.click(screen.getByText('Allow'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      const [formatted] = onSubmit.mock.calls[0];
      expect(formatted).toContain('Allow subagent: Allow');
    });

    it('falls back to localized defaults when labels are omitted', () => {
      const f: QuestionForm = {
        id: 'f', title: 'T',
        questions: [{ id: 'allow', label: 'Allow', type: 'yes-no' }],
      };
      render(<QuestionFormView form={f} interactive />);
      expect(screen.getByText('aiChat.questionForm.yes')).toBeInTheDocument();
      expect(screen.getByText('aiChat.questionForm.no')).toBeInTheDocument();
    });

    it('disables submit when required and unpicked', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
    });
  });

  describe('option-cards field', () => {
    const singleForm: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        {
          id: 'doc', label: 'Doc', type: 'option-cards', required: true,
          cards: [
            { id: 'blog', label: 'Blog', description: 'Story-driven', icon: 'feather' },
            { id: 'api', label: 'API', icon: 'code' },
          ],
        },
      ],
    };

    it('renders cards with their labels and descriptions', () => {
      render(<QuestionFormView form={singleForm} interactive />);
      expect(screen.getByText('Blog')).toBeInTheDocument();
      expect(screen.getByText('Story-driven')).toBeInTheDocument();
      expect(screen.getByText('API')).toBeInTheDocument();
    });

    it('selecting a card activates it and submits the card label', () => {
      const onSubmit = vi.fn();
      render(<QuestionFormView form={singleForm} interactive onSubmit={onSubmit} />);
      const card = screen.getByText('Blog').closest('button');
      fireEvent.click(card!);
      expect(card).toHaveClass('border-primary');
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      const [formatted] = onSubmit.mock.calls[0];
      expect(formatted).toContain('Doc: Blog');
    });

    it('icon precedence: with icon present, palette dots are not rendered', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          {
            id: 'doc', label: 'Doc', type: 'option-cards',
            cards: [{ id: 'a', label: 'A', icon: 'feather', palette: ['#fff', '#000'] }],
          },
        ],
      };
      const { container } = render(<QuestionFormView form={form} interactive />);
      const card = screen.getByText('A').closest('button')!;
      const dots = card.querySelectorAll('span[style*="background-color"]');
      expect(dots.length).toBe(0);
      expect(container.querySelector('svg')).not.toBeNull();
    });

    it('resolves allowlisted kebab-case icon names', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          {
            id: 'doc', label: 'Doc', type: 'option-cards',
            cards: [{ id: 'a', label: 'A', icon: 'layout-dashboard' }],
          },
        ],
      };
      const { container } = render(<QuestionFormView form={form} interactive />);
      expect(container.querySelector('svg')).not.toBeNull();
    });

    it('palette renders when icon is absent', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          {
            id: 'doc', label: 'Doc', type: 'option-cards',
            cards: [{ id: 'a', label: 'A', palette: ['#ff0000', '#00ff00'] }],
          },
        ],
      };
      render(<QuestionFormView form={form} interactive />);
      const card = screen.getByText('A').closest('button')!;
      const dots = card.querySelectorAll('span[style*="background-color"]');
      expect(dots.length).toBe(2);
    });

    it('multi-select includes stable card ids with the picked labels', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          {
            id: 'tags', label: 'Tags', type: 'option-cards', multiple: true,
            cards: [
              { id: 'a', label: 'Alpha' },
              { id: 'b', label: 'Bravo' },
              { id: 'c', label: 'Charlie' },
            ],
          },
        ],
      };
      const onSubmit = vi.fn();
      render(<QuestionFormView form={form} interactive onSubmit={onSubmit} />);
      fireEvent.click(screen.getByText('Alpha').closest('button')!);
      fireEvent.click(screen.getByText('Charlie').closest('button')!);
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      const [formatted] = onSubmit.mock.calls[0];
      expect(formatted).toContain(
        'Tags: Alpha [value: a], Charlie [value: c]',
      );
    });

    it('unknown icon name renders card without throwing', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          {
            id: 'doc', label: 'Doc', type: 'option-cards',
            cards: [
              { id: 'a', label: 'Alpha', description: 'Detail', icon: 'this-icon-does-not-exist' },
            ],
          },
        ],
      };
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('Alpha')).toBeInTheDocument();
      expect(screen.getByText('Detail')).toBeInTheDocument();
    });

    it('disables submit when required and no card picked', () => {
      render(<QuestionFormView form={singleForm} interactive />);
      expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
    });
  });

  describe('color field', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        {
          id: 'brand', label: 'Brand', type: 'color', required: true,
          swatches: ['#FF6B6B', '#4ECDC4'],
        },
      ],
    };

    it('renders swatches and the custom picker by default', () => {
      const { container } = render(<QuestionFormView form={form} interactive />);
      const swatchButtons = container.querySelectorAll('button[aria-label^="#"]');
      expect(swatchButtons.length).toBe(2);
      const colorInput = container.querySelector('input[type="color"]');
      expect(colorInput).not.toBeNull();
    });

    it('hides the custom picker when allow_custom is false', () => {
      const f: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          { id: 'brand', label: 'Brand', type: 'color', swatches: ['#000000'], allow_custom: false },
        ],
      };
      const { container } = render(<QuestionFormView form={f} interactive />);
      expect(container.querySelector('input[type="color"]')).toBeNull();
    });

    it('submits the picked swatch as lowercase hex', () => {
      const onSubmit = vi.fn();
      render(<QuestionFormView form={form} interactive onSubmit={onSubmit} />);
      fireEvent.click(screen.getByLabelText('#ff6b6b'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      const [formatted] = onSubmit.mock.calls[0];
      expect(formatted).toContain('Brand: #ff6b6b');
    });

    it('disables submit when required color is unpicked', () => {
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
    });
  });

  describe('unknown type', () => {
    it('renders nothing for the field but keeps the rest of the form usable', () => {
      const form: QuestionForm = {
        id: 'f', title: 'T',
        questions: [
          { id: 'mystery', label: 'Mystery', type: 'mystery-type' as never },
          { id: 'name', label: 'Name', type: 'text' },
        ],
      };
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('Mystery')).toBeInTheDocument();
      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /submit/i })).not.toBeDisabled();
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

  describe('default answers', () => {
    it('initializes single and multiple answers from defaults', () => {
      const form: QuestionForm = {
        id: 'defaults',
        title: 'Defaults',
        questions: [
          { id: 'kind', label: 'Kind', type: 'radio', options: ['App', 'Other'], default: 'App' },
          {
            id: 'features',
            label: 'Features',
            type: 'checkbox',
            options: ['Auth', 'Search'],
            default: ['Auth'],
          },
        ],
      };
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('App').closest('button')).toHaveClass('bg-primary');
      expect(screen.getByText('Auth').closest('button')).toHaveClass('bg-primary');
      expect(screen.getByText('Search').closest('button')).not.toHaveClass('bg-primary');
    });

    it('uses defaults to compute conditional visibility on first render', () => {
      const form: QuestionForm = {
        id: 'default-condition',
        title: 'Default condition',
        questions: [
          {
            id: 'kind',
            label: 'Kind',
            type: 'radio',
            options: ['App', 'Other'],
            default: 'Other',
          },
          {
            id: 'detail',
            label: 'Detail',
            type: 'text',
            show_if: { q: 'kind', eq: 'Other' },
          },
        ],
      };
      render(<QuestionFormView form={form} interactive />);
      expect(screen.getByText('Detail')).toBeInTheDocument();
    });

    it('prefers submitted answers over defaults during replay', () => {
      const form: QuestionForm = {
        id: 'submitted-over-default',
        title: 'Submitted over default',
        questions: [
          {
            id: 'kind',
            label: 'Kind',
            type: 'radio',
            options: ['App', 'Other'],
            default: 'Other',
          },
        ],
      };
      render(
        <QuestionFormView
          form={form}
          interactive={false}
          submittedAnswers={{ kind: 'App' }}
        />,
      );
      expect(screen.getByText('App').closest('button')).toHaveClass('bg-primary');
      expect(screen.getByText('Other').closest('button')).not.toHaveClass('bg-primary');
    });
  });

  describe('submit callback', () => {
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
      expect(screen.queryByText('aiChat.questionForm.answered')).toBeNull();
    });

    it('does not render submit button when locked', () => {
      render(<QuestionFormView form={baseForm} interactive={false} />);
      expect(screen.queryByRole('button', { name: /submit/i })).toBeNull();
    });

    it('locks while the answer is submitting', () => {
      render(<QuestionFormView form={baseForm} interactive isSubmitting />);
      expect(screen.queryByRole('button', { name: /submit/i })).toBeNull();
      expect(screen.queryByText('aiChat.questionForm.answered')).not.toBeInTheDocument();
    });

    it('does not show answered immediately after submit', () => {
      render(<QuestionFormView form={baseForm} interactive />);
      fireEvent.click(screen.getByText('Landing'));
      fireEvent.click(screen.getByRole('button', { name: /submit/i }));
      expect(screen.queryByText('aiChat.questionForm.answered')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
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
          submittedAnswers={{ type: 'Landing' }}
        />,
      );
      expect(screen.getByText('aiChat.questionForm.answered')).toBeInTheDocument();
    });
  });

  describe('conditional logic', () => {
    const condForm: QuestionForm = {
      id: 'cond', title: 'Conditional',
      questions: [
        { id: 'kind', label: 'Kind', type: 'radio', options: ['App', 'Other'], required: true },
        { id: 'detail', label: 'Detail', type: 'text', required: true, show_if: { q: 'kind', eq: 'Other' } },
      ],
    };

    it('hides conditional question until the trigger answer is selected', () => {
      render(<QuestionFormView form={condForm} interactive />);
      expect(screen.queryByText('Detail')).not.toBeInTheDocument();
      fireEvent.click(screen.getByText('Other'));
      expect(screen.getByText('Detail')).toBeInTheDocument();
    });

    it('does not count hidden required questions against submit readiness', () => {
      render(<QuestionFormView form={condForm} interactive />);
      fireEvent.click(screen.getByText('App'));
      expect(screen.getByRole('button', { name: 'aiChat.questionForm.submit' })).toBeEnabled();
    });

    it('keeps hidden answers and restores them when re-shown', () => {
      render(<QuestionFormView form={condForm} interactive />);
      fireEvent.click(screen.getByText('Other'));
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'kept' } });
      fireEvent.click(screen.getByText('App'));
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
      fireEvent.click(screen.getByText('Other'));
      expect(screen.getByRole('textbox')).toHaveValue('kept');
    });

    it('computes visibility from submitted answers on replay', () => {
      render(
        <QuestionFormView
          form={condForm}
          interactive={false}
          submittedAnswers={{ kind: 'App' }}
        />,
      );
      expect(screen.queryByText('Detail')).not.toBeInTheDocument();
    });

    const cityForm: QuestionForm = {
      id: 'city-form', title: 'City',
      questions: [
        { id: 'city', label: 'City', type: 'radio', options: ['Taipei', 'Kaohsiung'] },
        {
          id: 'district', label: 'District', type: 'radio',
          options_by: { q: 'city', map: { Taipei: ['Daan'], Kaohsiung: ['Zuoying'] } },
        },
      ],
    };

    it('switches dependent options and clears stale answers', () => {
      render(<QuestionFormView form={cityForm} interactive />);
      fireEvent.click(screen.getByText('Taipei'));
      fireEvent.click(screen.getByText('Daan'));
      expect(screen.getByText('Daan').closest('button')).toHaveClass('bg-primary');

      fireEvent.click(screen.getByText('Kaohsiung'));
      expect(screen.queryByText('Daan')).not.toBeInTheDocument();
      expect(screen.getByText('Zuoying').closest('button')).not.toHaveClass('bg-primary');
    });
  });
});
