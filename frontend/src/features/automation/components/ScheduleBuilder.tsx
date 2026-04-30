import React from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  createScheduleBuilderState,
  DEFAULT_SCHEDULE_STATE,
  formatScheduleStateToCron,
  type ScheduleBuilderMode,
  type ScheduleBuilderState,
  type ScheduleBuilderValidation,
  validateScheduleBuilderState,
} from './scheduleBuilderUtils';

interface ScheduleBuilderProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  onValidationChange?: (validation: ScheduleBuilderValidation) => void;
}

const MODE_OPTIONS: ScheduleBuilderMode[] = ['hourly', 'daily', 'weekly', 'monthly', 'advanced'];
const WEEKDAY_VALUES = [1, 2, 3, 4, 5, 6, 0];

const HOURS = Array.from({ length: 24 }, (_, index) => index);
const MINUTES = Array.from({ length: 60 }, (_, index) => index);
const MONTH_DAYS = Array.from({ length: 31 }, (_, index) => index + 1);

const padTime = (value: number): string => value.toString().padStart(2, '0');

const useScheduleBuilderState = (value: string): ScheduleBuilderState => {
  return React.useMemo(() => createScheduleBuilderState(value), [value]);
};

export const ScheduleBuilder: React.FC<ScheduleBuilderProps> = ({
  value,
  onChange,
  disabled = false,
  className,
  onValidationChange,
}) => {
  const { t } = useI18n();
  const state = useScheduleBuilderState(value);
  const validation = React.useMemo(() => validateScheduleBuilderState(state), [state]);

  React.useEffect(() => {
    onValidationChange?.(validation);
  }, [onValidationChange, validation]);

  const updateState = (nextState: ScheduleBuilderState) => {
    onChange(formatScheduleStateToCron(nextState));
  };

  const updateMode = (mode: ScheduleBuilderMode) => {
    if (mode === 'advanced') {
      updateState({
        ...state,
        mode,
        expression: value || formatScheduleStateToCron(DEFAULT_SCHEDULE_STATE),
      });
      return;
    }

    updateState({
      ...DEFAULT_SCHEDULE_STATE,
      ...state,
      mode,
      expression: '',
    });
  };

  const updateNumber = (key: 'hour' | 'minute' | 'dayOfMonth', nextValue: string) => {
    updateState({
      ...state,
      [key]: Number(nextValue),
    });
  };

  const toggleWeekday = (weekday: number) => {
    const weekdays = state.weekdays.includes(weekday)
      ? state.weekdays.filter((item) => item !== weekday)
      : [...state.weekdays, weekday].sort((a, b) => a - b);

    updateState({
      ...state,
      weekdays,
    });
  };

  const timeLabel = t('automation.form.scheduleBuilder.fields.time');
  const minuteLabel = t('automation.form.scheduleBuilder.fields.minute');
  const dayOfMonthLabel = t('automation.form.scheduleBuilder.fields.dayOfMonth');
  const summary = React.useMemo(() => {
    const time = `${padTime(state.hour)}:${padTime(state.minute)}`;

    switch (state.mode) {
      case 'hourly':
        return t('automation.form.scheduleBuilder.summary.hourly', { minute: padTime(state.minute) });
      case 'daily':
        return t('automation.form.scheduleBuilder.summary.daily', { time });
      case 'weekly':
        return t('automation.form.scheduleBuilder.summary.weekly', {
          time,
          weekdays: state.weekdays.map((weekday) => t(`automation.form.scheduleBuilder.weekdays.${weekday}`)).join(t('automation.form.scheduleBuilder.weekdaySeparator')),
        });
      case 'monthly':
        return t('automation.form.scheduleBuilder.summary.monthly', { time, day: state.dayOfMonth });
      case 'advanced':
        return t('automation.form.scheduleBuilder.summary.advanced', { cron: state.expression });
    }
  }, [state, t]);

  return (
    <div className={cn('space-y-3 rounded-md border border-border/60 bg-muted/20 p-3', className)}>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-2">
          <Label className="text-sm">{t('automation.form.scheduleBuilder.fields.mode')}</Label>
          <Select
            value={state.mode}
            onValueChange={(nextValue) => updateMode(nextValue as ScheduleBuilderMode)}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODE_OPTIONS.map((mode) => (
                <SelectItem key={mode} value={mode}>
                  {t(`automation.form.scheduleBuilder.modes.${mode}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {state.mode === 'hourly' ? (
          <div className="space-y-2">
            <Label className="text-sm">{minuteLabel}</Label>
            <Select
              value={String(state.minute)}
              onValueChange={(nextValue) => updateNumber('minute', nextValue)}
              disabled={disabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MINUTES.map((minute) => (
                  <SelectItem key={minute} value={String(minute)}>
                    {padTime(minute)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {state.mode !== 'hourly' && state.mode !== 'advanced' ? (
          <div className="space-y-2">
            <Label className="text-sm">{timeLabel}</Label>
            <div className="grid grid-cols-2 gap-2">
              <Select
                value={String(state.hour)}
                onValueChange={(nextValue) => updateNumber('hour', nextValue)}
                disabled={disabled}
              >
                <SelectTrigger aria-label={t('automation.form.scheduleBuilder.fields.hour')}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.map((hour) => (
                    <SelectItem key={hour} value={String(hour)}>
                      {padTime(hour)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={String(state.minute)}
                onValueChange={(nextValue) => updateNumber('minute', nextValue)}
                disabled={disabled}
              >
                <SelectTrigger aria-label={minuteLabel}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MINUTES.map((minute) => (
                    <SelectItem key={minute} value={String(minute)}>
                      {padTime(minute)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : null}
      </div>

      {state.mode === 'weekly' ? (
        <div className="space-y-2">
          <Label className="text-sm">{t('automation.form.scheduleBuilder.fields.weekdays')}</Label>
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
            {WEEKDAY_VALUES.map((weekday) => (
              <Button
                key={weekday}
                type="button"
                size="sm"
                variant={state.weekdays.includes(weekday) ? 'default' : 'outline'}
                disabled={disabled}
                onClick={() => toggleWeekday(weekday)}
                aria-pressed={state.weekdays.includes(weekday)}
              >
                {t(`automation.form.scheduleBuilder.weekdays.short.${weekday}`)}
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {state.mode === 'monthly' ? (
        <div className="space-y-2">
          <Label className="text-sm">{dayOfMonthLabel}</Label>
          <Select
            value={String(state.dayOfMonth)}
            onValueChange={(nextValue) => updateNumber('dayOfMonth', nextValue)}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MONTH_DAYS.map((day) => (
                <SelectItem key={day} value={String(day)}>
                  {t('automation.form.scheduleBuilder.dayOfMonthOption', { day })}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {state.mode === 'advanced' ? (
        <div className="space-y-2">
          <Label className="text-sm">{t('automation.form.scheduleBuilder.fields.advancedCron')}</Label>
          <Input
            value={state.expression}
            disabled={disabled}
            onChange={(event) => updateState({ ...state, expression: event.target.value })}
            placeholder={t('automation.form.scheduleBuilder.advancedPlaceholder')}
            className="font-mono"
          />
          <p className="text-xs text-muted-foreground">
            {t('automation.form.scheduleBuilder.advancedHelper')}
          </p>
        </div>
      ) : null}

      <div className="rounded-md border border-border/60 bg-background px-3 py-2">
        <p className="text-xs font-medium text-muted-foreground">
          {t('automation.form.scheduleBuilder.summaryLabel')}
        </p>
        <p className="mt-1 text-sm text-foreground">{summary}</p>
        <p className="mt-1 font-mono text-xs text-muted-foreground">{formatScheduleStateToCron(state)}</p>
      </div>

      {!validation.isValid && validation.errorKey ? (
        <p className="flex items-center gap-2 text-xs text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {t(validation.errorKey)}
        </p>
      ) : null}
    </div>
  );
};

export default ScheduleBuilder;
