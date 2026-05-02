import { describe, it, expect } from 'vitest';
import {
  splitOnQuestionForms,
  formatFormAnswers,
  parseSubmittedAnswers,
  type QuestionForm,
} from './question-form';

const makeForm = (id: string, title: string): QuestionForm => ({
  id,
  title,
  questions: [
    { id: 'type', label: 'Page type', type: 'radio', options: ['Landing', 'Dashboard'], required: true },
    { id: 'desc', label: 'Description', type: 'textarea' },
  ],
});

const formTag = (id: string, title: string, body: object) =>
  `<question-form id="${id}" title="${title}">${JSON.stringify(body)}</question-form>`;

describe('splitOnQuestionForms', () => {
  it('returns single text segment when no form present', () => {
    const result = splitOnQuestionForms('Hello world');
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ kind: 'text', content: 'Hello world' });
  });

  it('extracts valid single form', () => {
    const body = { questions: [{ id: 'q', label: 'Q', type: 'text' }] };
    const text = formTag('discovery', 'Brief', body);
    const result = splitOnQuestionForms(text);
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe('form');
    if (result[0].kind === 'form') {
      expect(result[0].form.id).toBe('discovery');
      expect(result[0].form.title).toBe('Brief');
      expect(result[0].form.questions).toHaveLength(1);
    }
  });

  it('preserves prose before and after form', () => {
    const body = { questions: [{ id: 'q', label: 'Q', type: 'radio', options: ['A', 'B'] }] };
    const text = `Before\n${formTag('f1', 'T', body)}\nAfter`;
    const result = splitOnQuestionForms(text);
    expect(result).toHaveLength(3);
    expect(result[0]).toEqual({ kind: 'text', content: 'Before\n' });
    expect(result[1].kind).toBe('form');
    expect(result[2]).toEqual({ kind: 'text', content: '\nAfter' });
  });

  it('falls back to text segment on malformed JSON', () => {
    const text = '<question-form id="f" title="T">{bad json}</question-form>';
    const result = splitOnQuestionForms(text);
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe('text');
    expect((result[0] as any).content).toContain('question-form');
  });

  it('handles multiple forms in one message', () => {
    const b = { questions: [{ id: 'q', label: 'Q', type: 'text' }] };
    const text = `${formTag('f1', 'First', b)}\n${formTag('f2', 'Second', b)}`;
    const result = splitOnQuestionForms(text);
    const forms = result.filter(s => s.kind === 'form');
    expect(forms).toHaveLength(2);
    expect((forms[0] as any).form.id).toBe('f1');
    expect((forms[1] as any).form.id).toBe('f2');
  });

  it('returns empty array for empty string', () => {
    const result = splitOnQuestionForms('');
    expect(result).toHaveLength(0);
  });
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
    expect(lines).toContain('Page type: Dashboard');
    expect(lines).toContain('Description: My desc');
  });

  it('skips questions with empty answers', () => {
    const form = makeForm('f', 'T');
    const answers = { type: 'Landing', desc: '' };
    const result = formatFormAnswers(form, answers);
    expect(result).not.toContain('Description:');
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
});

describe('parseSubmittedAnswers', () => {
  it('returns null when text is null', () => {
    expect(parseSubmittedAnswers('f', null)).toBeNull();
  });

  it('returns null when form id does not match', () => {
    const text = '[form answers — other]\nA: B';
    expect(parseSubmittedAnswers('f', text)).toBeNull();
  });

  it('parses matched form id and returns answers map', () => {
    const text = '[form answers — discovery]\nPage type: Landing\nDescription: My desc';
    const result = parseSubmittedAnswers('discovery', text);
    expect(result).not.toBeNull();
    expect(result!['Page type']).toBe('Landing');
    expect(result!['Description']).toBe('My desc');
  });

  it('returns empty object when no lines follow the prefix', () => {
    const text = '[form answers — f]';
    const result = parseSubmittedAnswers('f', text);
    expect(result).not.toBeNull();
    expect(Object.keys(result!)).toHaveLength(0);
  });
});
