export type QuestionType =
  | 'radio'
  | 'checkbox'
  | 'select'
  | 'text'
  | 'textarea'
  | 'direction-cards';

export interface DirectionCard {
  id: string;
  label: string;
  mood: string;
  palette: string[];
  displayFont: string;
  bodyFont: string;
}

export interface FormQuestion {
  id: string;
  label: string;
  type: QuestionType;
  options?: string[];
  cards?: DirectionCard[];
  placeholder?: string;
  required?: boolean;
}

export interface QuestionForm {
  id: string;
  title: string;
  questions: FormQuestion[];
}

export interface TextSegment {
  kind: 'text';
  content: string;
}

export interface FormSegment {
  kind: 'form';
  form: QuestionForm;
}

export type Segment = TextSegment | FormSegment;

const OPEN_RE = /<question-form([^>]*)>/g;
const CLOSE_TAG = '</question-form>';

function parseAttrs(raw: string): Record<string, string> {
  const out: Record<string, string> = {};
  const re = /(\w[\w-]*)="([^"]*)"/g;
  let m = re.exec(raw);
  while (m !== null) {
    out[m[1]] = m[2];
    m = re.exec(raw);
  }
  return out;
}

export function splitOnQuestionForms(text: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;
  OPEN_RE.lastIndex = 0;

  let match = OPEN_RE.exec(text);
  while (match !== null) {
    const openStart = match.index;
    const openEnd = openStart + match[0].length;
    const attrs = parseAttrs(match[1]);

    const closeIdx = text.indexOf(CLOSE_TAG, openEnd);
    if (closeIdx === -1) {
      match = OPEN_RE.exec(text);
      continue;
    }

    const body = text.slice(openEnd, closeIdx);
    const tagEnd = closeIdx + CLOSE_TAG.length;

    const before = text.slice(lastIndex, openStart);
    if (before) segments.push({ kind: 'text', content: before });

    let form: QuestionForm | null = null;
    try {
      const parsed = JSON.parse(body) as { title?: string; questions?: FormQuestion[] };
      if (Array.isArray(parsed.questions)) {
        form = {
          id: attrs['id'] ?? 'form',
          title: attrs['title'] ?? parsed.title ?? '',
          questions: parsed.questions,
        };
      }
    } catch {
      // fallback: treat entire tag as text
    }

    if (form) {
      segments.push({ kind: 'form', form });
    } else {
      const raw = text.slice(openStart, tagEnd);
      segments.push({ kind: 'text', content: raw });
    }

    lastIndex = tagEnd;
    OPEN_RE.lastIndex = tagEnd;
    match = OPEN_RE.exec(text);
  }

  const tail = text.slice(lastIndex);
  if (tail) segments.push({ kind: 'text', content: tail });

  return segments;
}

export function formatFormAnswers(
  form: QuestionForm,
  answers: Record<string, string | string[]>,
): string {
  const lines: string[] = [`[form answers — ${form.id}]`];
  for (const q of form.questions) {
    const val = answers[q.id];
    if (val === undefined || val === null) continue;
    const display = Array.isArray(val) ? val.join(', ') : val;
    if (display.trim()) lines.push(`${q.label}: ${display}`);
  }
  return lines.join('\n');
}

const ANSWERS_RE = /^\[form answers — ([^\]]+)\]\n?([\s\S]*)$/;

export function parseSubmittedAnswers(
  formId: string,
  userMessageText: string | null | undefined,
): Record<string, string> | null {
  if (!userMessageText) return null;
  const m = ANSWERS_RE.exec(userMessageText.trim());
  if (!m || m[1] !== formId) return null;

  const answers: Record<string, string> = {};
  const body = m[2] ?? '';
  for (const line of body.split('\n')) {
    const colon = line.indexOf(': ');
    if (colon === -1) continue;
    const label = line.slice(0, colon).trim();
    const value = line.slice(colon + 2).trim();
    if (label && value) answers[label] = value;
  }
  return answers;
}
