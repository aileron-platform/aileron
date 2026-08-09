export type QuestionType =
  | 'radio'
  | 'checkbox'
  | 'select'
  | 'text'
  | 'textarea'
  | 'number'
  | 'date'
  | 'yes-no'
  | 'option-cards'
  | 'color';

export type DateMode = 'date' | 'datetime';

export interface ShowIfCondition {
  q: string;            // referenced question id (must appear earlier in the form)
  eq?: string;          // answer equals (or contains, for array answers) this value
  in?: string[];        // answer is one of (or intersects, for array answers) these values
  not_empty?: boolean;  // question has any non-blank answer
}

export interface OptionsByRule {
  q: string;                      // source question id (must appear earlier in the form)
  map: Record<string, string[]>;  // source answer -> options
}

export interface OptionCard {
  id: string;
  label: string;
  description?: string;
  icon?: string;
  mood?: string;
  palette?: string[];
  displayFont?: string;
  bodyFont?: string;
}

export interface FormQuestion {
  id: string;
  label: string;
  type: QuestionType;
  options?: string[];
  cards?: OptionCard[];
  placeholder?: string;
  default?: string | string[];
  required?: boolean;
  min?: number | string;
  max?: number | string;
  step?: number;
  unit?: string;
  mode?: DateMode;
  yes_label?: string;
  no_label?: string;
  multiple?: boolean;
  swatches?: string[];
  allow_custom?: boolean;
  show_if?: ShowIfCondition;
  options_by?: OptionsByRule;
}

export interface QuestionForm {
  id: string;
  title: string;
  questions: FormQuestion[];
}

function answerValues(value: string | string[] | undefined): string[] {
  if (Array.isArray(value)) {
    return value.filter(v => typeof v === 'string' && v.trim() !== '');
  }
  if (typeof value === 'string' && value.trim() !== '') return [value];
  return [];
}

function conditionMatches(cond: ShowIfCondition, values: string[]): boolean {
  if (typeof cond.eq === 'string') return values.includes(cond.eq);
  if (Array.isArray(cond.in)) return cond.in.some(v => values.includes(v));
  if (cond.not_empty === true) return values.length > 0;
  // No usable operator: treat the condition as invalid and keep the question visible
  return true;
}

function isEarlierQuestion(questions: FormQuestion[], index: number, id: string): boolean {
  return questions.slice(0, index).some(q => q.id === id);
}

export function computeVisibleQuestions(
  form: QuestionForm,
  answers: Record<string, string | string[]>,
): FormQuestion[] {
  const questions = form.questions ?? [];
  const hidden = new Set<string>();
  const visible: FormQuestion[] = [];

  questions.forEach((question, index) => {
    const cond = question.show_if;
    // Invalid references (later question, self, unknown id) keep the question visible
    if (cond && typeof cond.q === 'string' && isEarlierQuestion(questions, index, cond.q)) {
      const values = hidden.has(cond.q) ? [] : answerValues(answers[cond.q]);
      if (!conditionMatches(cond, values)) {
        hidden.add(question.id);
        return;
      }
    }
    visible.push(question);
  });

  return visible;
}

export function resolveQuestionOptions(
  question: FormQuestion,
  form: QuestionForm,
  answers: Record<string, string | string[]>,
): string[] {
  const fallback = question.options ?? [];
  const rule = question.options_by;
  if (!rule || typeof rule.q !== 'string') return fallback;
  if (!rule.map || typeof rule.map !== 'object' || Array.isArray(rule.map)) return fallback;

  const questions = form.questions ?? [];
  const selfIndex = questions.findIndex(q => q.id === question.id);
  if (selfIndex === -1 || !isEarlierQuestion(questions, selfIndex, rule.q)) return fallback;

  const sourceVisible = computeVisibleQuestions(form, answers).some(q => q.id === rule.q);
  const values = sourceVisible ? answerValues(answers[rule.q]) : [];
  if (values.length === 0) return fallback;

  const resolved: string[] = [];
  let anyHit = false;
  for (const value of values) {
    const mapped = rule.map[value];
    if (!Array.isArray(mapped)) continue;
    anyHit = true;
    for (const opt of mapped) {
      if (typeof opt === 'string' && !resolved.includes(opt)) resolved.push(opt);
    }
  }
  return anyHit ? resolved : fallback;
}

const OPTION_QUESTION_TYPES: ReadonlySet<QuestionType> = new Set(['radio', 'checkbox', 'select']);

export function cleanupAnswers(
  form: QuestionForm,
  answers: Record<string, string | string[]>,
): Record<string, string | string[]> {
  const next = { ...answers };
  // Questions only reference earlier ones, so a single in-order pass settles cascades
  for (const question of form.questions ?? []) {
    if (!question.options_by || !OPTION_QUESTION_TYPES.has(question.type)) continue;
    const options = resolveQuestionOptions(question, form, next);
    const value = next[question.id];
    if (Array.isArray(value)) {
      const filtered = value.filter(v => options.includes(v));
      if (filtered.length !== value.length) next[question.id] = filtered;
    } else if (typeof value === 'string' && value !== '' && !options.includes(value)) {
      next[question.id] = '';
    }
  }
  return next;
}

export function formatFormAnswers(
  form: QuestionForm,
  answers: Record<string, string | string[]>,
): string {
  const lines: string[] = [`[form answers — ${form.id}]`];
  for (const q of computeVisibleQuestions(form, answers)) {
    const val = answers[q.id];
    const values = answerValues(val);
    if (values.length === 0) {
      lines.push(`- ${q.label}: (skipped)`);
      continue;
    }
    const display = values.map(value => {
      if (q.type !== 'option-cards') return value;
      const card = q.cards?.find(candidate => candidate.label === value);
      return card && card.id !== card.label
        ? `${card.label} [value: ${card.id}]`
        : value;
    });
    lines.push(`- ${q.label}: ${display.join(', ')}`);
  }
  return lines.join('\n');
}

const QUESTION_TYPES: ReadonlySet<string> = new Set([
  'radio',
  'checkbox',
  'select',
  'text',
  'textarea',
  'number',
  'date',
  'yes-no',
  'option-cards',
  'color',
]);

const stringArray = (value: unknown): string[] | undefined =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : undefined;

export function parseQuestionForm(
  parameters: Record<string, unknown>,
): QuestionForm | null {
  const { id, title, questions } = parameters;
  if (typeof id !== 'string' || typeof title !== 'string' || !Array.isArray(questions)) {
    return null;
  }

  const parsed: FormQuestion[] = [];
  for (const raw of questions) {
    if (typeof raw !== 'object' || raw === null) return null;
    const question = raw as FormQuestion;
    if (
      typeof question.id !== 'string' ||
      typeof question.label !== 'string' ||
      !QUESTION_TYPES.has(String(question.type))
    ) {
      return null;
    }

    parsed.push({
      ...question,
      default:
        typeof question.default === 'string'
          ? question.default
          : stringArray(question.default),
      options: stringArray(question.options),
      swatches: stringArray(question.swatches),
      cards: Array.isArray(question.cards)
        ? question.cards.filter(
            (card): card is OptionCard =>
              typeof card === 'object' &&
              card !== null &&
              typeof card.id === 'string' &&
              typeof card.label === 'string',
          )
        : undefined,
      show_if:
        typeof question.show_if === 'object' &&
        question.show_if !== null &&
        typeof question.show_if.q === 'string'
          ? question.show_if
          : undefined,
      options_by:
        typeof question.options_by === 'object' &&
        question.options_by !== null &&
        typeof question.options_by.q === 'string' &&
        typeof question.options_by.map === 'object' &&
        question.options_by.map !== null
          ? question.options_by
          : undefined,
    });
  }

  if (parsed.length === 0) return null;
  return { id, title, questions: parsed };
}
