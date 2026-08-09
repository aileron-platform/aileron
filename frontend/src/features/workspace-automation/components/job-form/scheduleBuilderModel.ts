export type ScheduleBuilderMode = 'hourly' | 'daily' | 'weekly' | 'monthly' | 'advanced';

export interface ScheduleBuilderState {
  mode: ScheduleBuilderMode;
  minute: number;
  hour: number;
  weekdays: number[];
  dayOfMonth: number;
  expression: string;
}

export interface ScheduleBuilderValidation {
  isValid: boolean;
  errorKey?: string;
}

export const DEFAULT_SCHEDULE_EXPRESSION = '0 9 * * *';

export const DEFAULT_SCHEDULE_STATE: ScheduleBuilderState = {
  mode: 'daily',
  minute: 0,
  hour: 9,
  weekdays: [1],
  dayOfMonth: 1,
  expression: DEFAULT_SCHEDULE_EXPRESSION,
};

const isIntegerInRange = (value: string, min: number, max: number): boolean => {
  if (!/^\d+$/.test(value)) {
    return false;
  }
  const numberValue = Number(value);
  return Number.isInteger(numberValue) && numberValue >= min && numberValue <= max;
};

const isValidCronField = (field: string, min: number, max: number): boolean => {
  return field.split(',').every((segment) => {
    const [base, step] = segment.split('/');
    if (step !== undefined && (!/^\d+$/.test(step) || Number(step) < 1)) {
      return false;
    }
    if (base === '*') {
      return true;
    }
    if (/^\d+$/.test(base)) {
      return isIntegerInRange(base, min, max);
    }
    const rangeMatch = base.match(/^(\d+)-(\d+)$/);
    if (!rangeMatch) {
      return false;
    }
    const start = Number(rangeMatch[1]);
    const end = Number(rangeMatch[2]);
    return start <= end && start >= min && end <= max;
  });
};

const parseInteger = (value: string, min: number, max: number): number | null => {
  return isIntegerInRange(value, min, max) ? Number(value) : null;
};

const parseWeekdays = (value: string): number[] | null => {
  if (!/^\d(,\d)*$/.test(value)) {
    return null;
  }
  const days = value.split(',').map(Number);
  if (days.some((day) => day < 0 || day > 6)) {
    return null;
  }
  return Array.from(new Set(days)).sort((a, b) => a - b);
};

export const formatScheduleStateToCron = (state: ScheduleBuilderState): string => {
  const minute = Math.trunc(state.minute);
  const hour = Math.trunc(state.hour);
  const dayOfMonth = Math.trunc(state.dayOfMonth);

  switch (state.mode) {
    case 'hourly':
      return `${minute} * * * *`;
    case 'daily':
      return `${minute} ${hour} * * *`;
    case 'weekly':
      return `${minute} ${hour} * * ${state.weekdays.join(',')}`;
    case 'monthly':
      return `${minute} ${hour} ${dayOfMonth} * *`;
    case 'advanced':
      return state.expression;
  }
};

export const parseCronExpression = (expression: string): ScheduleBuilderState => {
  const trimmed = expression.trim();
  const parts = trimmed.split(/\s+/);

  if (parts.length !== 5) {
    return {
      ...DEFAULT_SCHEDULE_STATE,
      mode: 'advanced',
      expression,
    };
  }

  const [minutePart, hourPart, dayOfMonthPart, monthPart, weekdayPart] = parts;
  const minute = parseInteger(minutePart, 0, 59);
  const hour = parseInteger(hourPart, 0, 23);

  if (minute !== null && hourPart === '*' && dayOfMonthPart === '*' && monthPart === '*' && weekdayPart === '*') {
    return {
      ...DEFAULT_SCHEDULE_STATE,
      mode: 'hourly',
      minute,
      expression: trimmed,
    };
  }

  if (minute !== null && hour !== null && dayOfMonthPart === '*' && monthPart === '*' && weekdayPart === '*') {
    return {
      ...DEFAULT_SCHEDULE_STATE,
      mode: 'daily',
      minute,
      hour,
      expression: trimmed,
    };
  }

  const weekdays = parseWeekdays(weekdayPart);
  if (minute !== null && hour !== null && dayOfMonthPart === '*' && monthPart === '*' && weekdays && weekdays.length > 0) {
    return {
      ...DEFAULT_SCHEDULE_STATE,
      mode: 'weekly',
      minute,
      hour,
      weekdays,
      expression: trimmed,
    };
  }

  const dayOfMonth = parseInteger(dayOfMonthPart, 1, 31);
  if (minute !== null && hour !== null && dayOfMonth !== null && monthPart === '*' && weekdayPart === '*') {
    return {
      ...DEFAULT_SCHEDULE_STATE,
      mode: 'monthly',
      minute,
      hour,
      dayOfMonth,
      expression: trimmed,
    };
  }

  return {
    ...DEFAULT_SCHEDULE_STATE,
    mode: 'advanced',
    expression,
  };
};

export const isValidCronExpression = (expression: string): boolean => {
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5) {
    return false;
  }
  const [minute, hour, dayOfMonth, month, weekday] = parts;
  return isValidCronField(minute, 0, 59)
    && isValidCronField(hour, 0, 23)
    && isValidCronField(dayOfMonth, 1, 31)
    && isValidCronField(month, 1, 12)
    && isValidCronField(weekday, 0, 6);
};

export const validateScheduleBuilderState = (state: ScheduleBuilderState): ScheduleBuilderValidation => {
  if (state.mode === 'weekly' && state.weekdays.length === 0) {
    return {
      isValid: false,
      errorKey: 'automation.form.scheduleBuilder.validation.weekdayRequired',
    };
  }

  if (state.mode === 'advanced' && !isValidCronExpression(state.expression)) {
    return {
      isValid: false,
      errorKey: 'automation.form.scheduleBuilder.validation.invalidCron',
    };
  }

  return { isValid: true };
};

export const createScheduleBuilderState = (value: string): ScheduleBuilderState => {
  return parseCronExpression(value || DEFAULT_SCHEDULE_EXPRESSION);
};
