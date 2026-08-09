import { describe, it, expect } from 'vitest';
import {
  computeVisibleQuestions,
  resolveQuestionOptions,
  cleanupAnswers,
  formatFormAnswers,
  parseQuestionForm,
  type QuestionForm,
} from './questionFormModel';

const makeForm = (id: string, title: string): QuestionForm => ({
  id,
  title,
  questions: [
    { id: 'type', label: 'Page type', type: 'radio', options: ['Landing', 'Dashboard'], required: true },
    { id: 'desc', label: 'Description', type: 'textarea' },
  ],
});

describe('formatFormAnswers', () => {
  it('produces correct prefix with form id', () => {
    const form = makeForm('discovery', 'Brief');
    const answers = { type: 'Landing', desc: 'A landing page' };
    const result = formatFormAnswers(form, answers);
    expect(result.startsWith('[form answers — discovery]')).toBe(true);
  });

  it('includes each answered question on a new line', () => {
    const form = makeForm('f', 'T');
    const answers = { type: 'Dashboard', desc: 'My desc' };
    const lines = formatFormAnswers(form, answers).split('\n');
    expect(lines).toContain('- Page type: Dashboard');
    expect(lines).toContain('- Description: My desc');
  });

  it('marks questions with empty answers as skipped', () => {
    const form = makeForm('f', 'T');
    const answers = { type: 'Landing', desc: '' };
    const result = formatFormAnswers(form, answers);
    expect(result).toContain('- Description: (skipped)');
  });

  it('marks missing answers as skipped', () => {
    const form = makeForm('f', 'T');
    const result = formatFormAnswers(form, { type: 'Landing' });
    expect(result).toContain('- Description: (skipped)');
  });

  it('joins array answers with comma', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'feat', label: 'Features', type: 'checkbox', options: ['A', 'B', 'C'] }],
    };
    const answers = { feat: ['A', 'C'] };
    const result = formatFormAnswers(form, answers);
    expect(result).toContain('Features: A, C');
  });

  it('joins option-cards multi-select labels with comma-space', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        {
          id: 'docs',
          label: 'Docs',
          type: 'option-cards',
          multiple: true,
          cards: [
            { id: 'a', label: 'Alpha' },
            { id: 'b', label: 'Bravo' },
            { id: 'c', label: 'Charlie' },
          ],
        },
      ],
    };
    const result = formatFormAnswers(form, { docs: ['Alpha', 'Charlie'] });
    expect(result).toContain('Docs: Alpha [value: a], Charlie [value: c]');
  });

  it('does not repeat option-card value when id equals label', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        {
          id: 'docs',
          label: 'Docs',
          type: 'option-cards',
          cards: [{ id: 'Alpha', label: 'Alpha' }],
        },
      ],
    };
    expect(formatFormAnswers(form, { docs: 'Alpha' })).toContain('- Docs: Alpha');
    expect(formatFormAnswers(form, { docs: 'Alpha' })).not.toContain('[value:');
  });

  it('does not leak number.unit into the answer payload', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [{ id: 'pages', label: 'Pages', type: 'number', unit: 'pg' }],
    };
    const result = formatFormAnswers(form, { pages: '10' });
    expect(result).toContain('Pages: 10');
    expect(result).not.toContain('pg');
  });

  it('omits answers of hidden questions', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'kind', label: 'Kind', type: 'radio', options: ['App', 'Other'] },
        { id: 'detail', label: 'Detail', type: 'text', show_if: { q: 'kind', eq: 'Other' } },
      ],
    };
    const result = formatFormAnswers(form, { kind: 'App', detail: 'stale text' });
    expect(result).toContain('Kind: App');
    expect(result).not.toContain('Detail:');
  });
});

describe('computeVisibleQuestions', () => {
  const condForm: QuestionForm = {
    id: 'f', title: 'T',
    questions: [
      { id: 'kind', label: 'Kind', type: 'radio', options: ['App', 'Other'] },
      { id: 'detail', label: 'Detail', type: 'text', show_if: { q: 'kind', eq: 'Other' } },
    ],
  };

  it('shows all questions when no condition exists', () => {
    const form = makeForm('f', 'T');
    const visible = computeVisibleQuestions(form, {});
    expect(visible.map(q => q.id)).toEqual(['type', 'desc']);
  });

  it('hides question when eq condition does not match', () => {
    expect(computeVisibleQuestions(condForm, { kind: 'App' }).map(q => q.id)).toEqual(['kind']);
  });

  it('hides question when source is unanswered', () => {
    expect(computeVisibleQuestions(condForm, {}).map(q => q.id)).toEqual(['kind']);
  });

  it('shows question when eq condition matches', () => {
    expect(computeVisibleQuestions(condForm, { kind: 'Other' }).map(q => q.id)).toEqual(['kind', 'detail']);
  });

  it('supports in condition', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'level', label: 'Level', type: 'radio', options: ['Low', 'Mid', 'High'] },
        { id: 'why', label: 'Why', type: 'text', show_if: { q: 'level', in: ['Mid', 'High'] } },
      ],
    };
    expect(computeVisibleQuestions(form, { level: 'Mid' }).map(q => q.id)).toEqual(['level', 'why']);
    expect(computeVisibleQuestions(form, { level: 'Low' }).map(q => q.id)).toEqual(['level']);
  });

  it('supports not_empty condition', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'name', label: 'Name', type: 'text' },
        { id: 'suffix', label: 'Suffix', type: 'text', show_if: { q: 'name', not_empty: true } },
      ],
    };
    expect(computeVisibleQuestions(form, { name: '  ' }).map(q => q.id)).toEqual(['name']);
    expect(computeVisibleQuestions(form, { name: 'A' }).map(q => q.id)).toEqual(['name', 'suffix']);
  });

  it('treats eq as contains for array answers', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'feat', label: 'Features', type: 'checkbox', options: ['A', 'B'] },
        { id: 'extra', label: 'Extra', type: 'text', show_if: { q: 'feat', eq: 'B' } },
      ],
    };
    expect(computeVisibleQuestions(form, { feat: ['A', 'B'] }).map(q => q.id)).toEqual(['feat', 'extra']);
    expect(computeVisibleQuestions(form, { feat: ['A'] }).map(q => q.id)).toEqual(['feat']);
  });

  it('ignores condition referencing a later question', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'text', show_if: { q: 'b', eq: 'x' } },
        { id: 'b', label: 'B', type: 'text' },
      ],
    };
    expect(computeVisibleQuestions(form, {}).map(q => q.id)).toEqual(['a', 'b']);
  });

  it('ignores condition referencing an unknown or self id', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'text', show_if: { q: 'missing', eq: 'x' } },
        { id: 'b', label: 'B', type: 'text', show_if: { q: 'b', eq: 'x' } },
      ],
    };
    expect(computeVisibleQuestions(form, {}).map(q => q.id)).toEqual(['a', 'b']);
  });

  it('ignores condition without any usable operator', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'text' },
        { id: 'b', label: 'B', type: 'text', show_if: { q: 'a' } },
      ],
    };
    expect(computeVisibleQuestions(form, {}).map(q => q.id)).toEqual(['a', 'b']);
  });

  it('cascades hiding through chained conditions', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'q1', label: 'Q1', type: 'radio', options: ['yes', 'no'] },
        { id: 'q2', label: 'Q2', type: 'text', show_if: { q: 'q1', eq: 'yes' } },
        { id: 'q3', label: 'Q3', type: 'text', show_if: { q: 'q2', not_empty: true } },
      ],
    };
    // q2 still holds a stale answer but is hidden, so q3 must hide too
    expect(computeVisibleQuestions(form, { q1: 'no', q2: 'stale' }).map(q => q.id)).toEqual(['q1']);
  });
});

describe('parseQuestionForm', () => {
  it('parses a valid tool parameters payload', () => {
    const form = parseQuestionForm({
      id: 'color',
      title: 'Pick a color',
      questions: [
        {
          id: 'favorite',
          label: 'Favorite color',
          type: 'radio',
          options: ['red'],
        },
      ],
    });
    expect(form?.questions).toHaveLength(1);
  });

  it('parses string and array defaults', () => {
    const form = parseQuestionForm({
      id: 'defaults',
      title: 'Defaults',
      questions: [
        { id: 'kind', label: 'Kind', type: 'radio', default: 'App' },
        { id: 'features', label: 'Features', type: 'checkbox', default: ['Auth', 'Search'] },
      ],
    });
    expect(form?.questions[0]?.default).toBe('App');
    expect(form?.questions[1]?.default).toEqual(['Auth', 'Search']);
  });

  it('drops malformed defaults', () => {
    const form = parseQuestionForm({
      id: 'defaults',
      title: 'Defaults',
      questions: [
        { id: 'kind', label: 'Kind', type: 'radio', default: 42 },
      ],
    });
    expect(form?.questions[0]?.default).toBeUndefined();
  });

  it.each([
    [{}],
    [{ id: 'x', title: 'y', questions: [] }],
    [{ id: 'x', title: 'y', questions: [{ id: 'q', label: 'l', type: 'nope' }] }],
  ])('returns null for invalid payload %#', (parameters) => {
    expect(parseQuestionForm(parameters as Record<string, unknown>)).toBeNull();
  });

  it('sanitizes malformed nested fields instead of failing', () => {
    const form = parseQuestionForm({
      id: 'x',
      title: 'y',
      questions: [
        {
          id: 'q',
          label: 'l',
          type: 'radio',
          options: ['ok', 42, null],
          show_if: { nope: true },
          options_by: 'garbage',
          cards: [{ id: 'c', label: 'C' }, 'junk'],
        },
      ],
    });
    expect(form?.questions[0]?.options).toEqual(['ok']);
    expect(form?.questions[0]?.show_if).toBeUndefined();
    expect(form?.questions[0]?.options_by).toBeUndefined();
    expect(form?.questions[0]?.cards).toEqual([{ id: 'c', label: 'C' }]);
  });
});

describe('resolveQuestionOptions', () => {
  const cityForm: QuestionForm = {
    id: 'f', title: 'T',
    questions: [
      { id: 'city', label: 'City', type: 'radio', options: ['Taipei', 'Kaohsiung'] },
      {
        id: 'district', label: 'District', type: 'select',
        options: ['(pick a city first)'],
        options_by: { q: 'city', map: { Taipei: ['Daan', 'Xinyi'], Kaohsiung: ['Zuoying', 'Lingya'] } },
      },
    ],
  };
  const district = cityForm.questions[1];

  it('returns static options when no rule exists', () => {
    expect(resolveQuestionOptions(cityForm.questions[0], cityForm, {})).toEqual(['Taipei', 'Kaohsiung']);
  });

  it('returns mapped options when source answer hits the map', () => {
    expect(resolveQuestionOptions(district, cityForm, { city: 'Taipei' })).toEqual(['Daan', 'Xinyi']);
  });

  it('falls back to static options when source is unanswered', () => {
    expect(resolveQuestionOptions(district, cityForm, {})).toEqual(['(pick a city first)']);
  });

  it('falls back to static options when the map misses', () => {
    expect(resolveQuestionOptions(district, cityForm, { city: 'Tainan' })).toEqual(['(pick a city first)']);
  });

  it('returns empty list on map miss without static options', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'radio', options: ['x'] },
        { id: 'b', label: 'B', type: 'select', options_by: { q: 'a', map: { y: ['1'] } } },
      ],
    };
    expect(resolveQuestionOptions(form.questions[1], form, { a: 'x' })).toEqual([]);
  });

  it('unions and dedupes options for array source answers', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'tags', label: 'Tags', type: 'checkbox', options: ['a', 'b'] },
        { id: 'sub', label: 'Sub', type: 'checkbox', options_by: { q: 'tags', map: { a: ['1', '2'], b: ['2', '3'] } } },
      ],
    };
    expect(resolveQuestionOptions(form.questions[1], form, { tags: ['a', 'b'] })).toEqual(['1', '2', '3']);
  });

  it('falls back to static options when source question is hidden', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'gate', label: 'Gate', type: 'radio', options: ['on', 'off'] },
        { id: 'src', label: 'Src', type: 'radio', options: ['x'], show_if: { q: 'gate', eq: 'on' } },
        { id: 'dep', label: 'Dep', type: 'select', options: ['default'], options_by: { q: 'src', map: { x: ['mapped'] } } },
      ],
    };
    expect(resolveQuestionOptions(form.questions[2], form, { gate: 'off', src: 'x' })).toEqual(['default']);
  });

  it('falls back to static options for invalid references', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'select', options: ['keep'], options_by: { q: 'later', map: { x: ['1'] } } },
        { id: 'later', label: 'L', type: 'radio', options: ['x'] },
      ],
    };
    expect(resolveQuestionOptions(form.questions[0], form, { later: 'x' })).toEqual(['keep']);
  });

  it('falls back to static options when map is not an object', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'radio', options: ['x'] },
        {
          id: 'b', label: 'B', type: 'select', options: ['keep'],
          options_by: { q: 'a', map: ['bad'] as unknown as Record<string, string[]> },
        },
      ],
    };
    expect(resolveQuestionOptions(form.questions[1], form, { a: 'x' })).toEqual(['keep']);
  });
});

describe('cleanupAnswers', () => {
  const cityForm: QuestionForm = {
    id: 'f', title: 'T',
    questions: [
      { id: 'city', label: 'City', type: 'radio', options: ['Taipei', 'Kaohsiung'] },
      {
        id: 'district', label: 'District', type: 'select',
        options_by: { q: 'city', map: { Taipei: ['Daan'], Kaohsiung: ['Zuoying'] } },
      },
    ],
  };

  it('clears a single-value answer no longer in the resolved options', () => {
    const next = cleanupAnswers(cityForm, { city: 'Kaohsiung', district: 'Daan' });
    expect(next.district).toBe('');
  });

  it('keeps a single-value answer still in the resolved options', () => {
    const next = cleanupAnswers(cityForm, { city: 'Taipei', district: 'Daan' });
    expect(next.district).toBe('Daan');
  });

  it('filters array answers down to valid options', () => {
    const form: QuestionForm = {
      id: 'f', title: 'T',
      questions: [
        { id: 'a', label: 'A', type: 'radio', options: ['x', 'y'] },
        { id: 'b', label: 'B', type: 'checkbox', options_by: { q: 'a', map: { x: ['1', '2'], y: ['2'] } } },
      ],
    };
    const next = cleanupAnswers(form, { a: 'y', b: ['1', '2'] });
    expect(next.b).toEqual(['2']);
  });

  it('leaves questions without options_by untouched', () => {
    const next = cleanupAnswers(cityForm, { city: 'Taipei' });
    expect(next.city).toBe('Taipei');
  });
});
