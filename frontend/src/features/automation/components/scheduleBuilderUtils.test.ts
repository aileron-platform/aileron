import { describe, expect, it } from 'vitest';
import {
  createScheduleBuilderState,
  formatScheduleStateToCron,
  isValidCronExpression,
  validateScheduleBuilderState,
  type ScheduleBuilderState,
} from './scheduleBuilderUtils';

const baseState: ScheduleBuilderState = {
  mode: 'daily',
  minute: 0,
  hour: 9,
  weekdays: [1],
  dayOfMonth: 1,
  expression: '0 9 * * *',
};

describe('scheduleBuilderUtils', () => {
  it('generates cron expressions for supported structured modes', () => {
    expect(formatScheduleStateToCron({ ...baseState, mode: 'hourly', minute: 15 })).toBe('15 * * * *');
    expect(formatScheduleStateToCron({ ...baseState, mode: 'daily', hour: 8, minute: 30 })).toBe('30 8 * * *');
    expect(formatScheduleStateToCron({ ...baseState, mode: 'weekly', hour: 8, minute: 30, weekdays: [1, 3, 5] })).toBe('30 8 * * 1,3,5');
    expect(formatScheduleStateToCron({ ...baseState, mode: 'monthly', hour: 10, minute: 0, dayOfMonth: 15 })).toBe('0 10 15 * *');
  });

  it('parses supported cron expressions into builder state', () => {
    expect(createScheduleBuilderState('15 * * * *')).toMatchObject({ mode: 'hourly', minute: 15 });
    expect(createScheduleBuilderState('0 9 * * *')).toMatchObject({ mode: 'daily', hour: 9, minute: 0 });
    expect(createScheduleBuilderState('30 8 * * 1,3,5')).toMatchObject({
      mode: 'weekly',
      hour: 8,
      minute: 30,
      weekdays: [1, 3, 5],
    });
    expect(createScheduleBuilderState('0 10 15 * *')).toMatchObject({
      mode: 'monthly',
      hour: 10,
      minute: 0,
      dayOfMonth: 15,
    });
  });

  it('falls back unsupported cron expressions to advanced mode without normalization', () => {
    expect(createScheduleBuilderState('*/15 9-17 * * 1-5')).toMatchObject({
      mode: 'advanced',
      expression: '*/15 9-17 * * 1-5',
    });
  });

  it('validates incomplete weekly schedules and invalid advanced cron values', () => {
    expect(validateScheduleBuilderState({ ...baseState, mode: 'weekly', weekdays: [] })).toEqual({
      isValid: false,
      errorKey: 'automation.form.scheduleBuilder.validation.weekdayRequired',
    });
    expect(validateScheduleBuilderState({ ...baseState, mode: 'advanced', expression: 'invalid cron' })).toEqual({
      isValid: false,
      errorKey: 'automation.form.scheduleBuilder.validation.invalidCron',
    });
    expect(isValidCronExpression('0 9 * * *')).toBe(true);
    expect(isValidCronExpression('*/15 9-17 * * 1-5')).toBe(true);
    expect(isValidCronExpression('99 9 * * *')).toBe(false);
    expect(isValidCronExpression('invalid cron')).toBe(false);
  });
});
