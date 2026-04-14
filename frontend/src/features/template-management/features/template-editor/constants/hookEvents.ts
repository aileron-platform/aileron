export interface HookEventOption {
  value: string;
  labelKey: string;
  descriptionKey: string;
}

export const EVENT_OPTIONS: HookEventOption[] = [
  {
    value: 'PreToolUse',
    labelKey: 'template.editor.hooks.events.preToolUse.label',
    descriptionKey: 'template.editor.hooks.events.preToolUse.description'
  },
  {
    value: 'PostToolUse',
    labelKey: 'template.editor.hooks.events.postToolUse.label',
    descriptionKey: 'template.editor.hooks.events.postToolUse.description'
  },
  {
    value: 'UserPromptSubmit',
    labelKey: 'template.editor.hooks.events.userPromptSubmit.label',
    descriptionKey: 'template.editor.hooks.events.userPromptSubmit.description'
  },
  {
    value: 'Notification',
    labelKey: 'template.editor.hooks.events.notification.label',
    descriptionKey: 'template.editor.hooks.events.notification.description'
  },
  {
    value: 'Stop',
    labelKey: 'template.editor.hooks.events.stop.label',
    descriptionKey: 'template.editor.hooks.events.stop.description'
  },
  {
    value: 'SubagentStop',
    labelKey: 'template.editor.hooks.events.subagentStop.label',
    descriptionKey: 'template.editor.hooks.events.subagentStop.description'
  },
  {
    value: 'PreCompact',
    labelKey: 'template.editor.hooks.events.preCompact.label',
    descriptionKey: 'template.editor.hooks.events.preCompact.description'
  },
  {
    value: 'SessionStart',
    labelKey: 'template.editor.hooks.events.sessionStart.label',
    descriptionKey: 'template.editor.hooks.events.sessionStart.description'
  },
  {
    value: 'SessionEnd',
    labelKey: 'template.editor.hooks.events.sessionEnd.label',
    descriptionKey: 'template.editor.hooks.events.sessionEnd.description'
  }
];

export const getEventDescription = (
  event: string,
  t: (key: string, params?: Record<string, string | number>) => string
): string => {
  const option = EVENT_OPTIONS.find(opt => opt.value === event);
  return option ? t(option.labelKey) : event;
};