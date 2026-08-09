import type { HookDialogLabels, HookDialogOptions } from '../HookDialog';
import { HOOK_TYPES } from '../model/providerHookSpec';

export const createHookDialogTestLabels = (
  matcherPatternHelp: HookDialogLabels['matcherActions']['matcherPatternHelp'] = () => ['Pattern help'],
): HookDialogLabels => ({
  title: 'Add hook',
  description: 'Configure hook.',
  cancel: 'Cancel',
  submit: 'Create hook',
  name: {
    label: 'Name',
    placeholder: 'Name placeholder',
  },
  scope: {
    label: 'Scope',
    requiredLabel: 'Scope',
    placeholder: 'Choose scope',
  },
  event: {
    label: 'Event type',
    placeholder: 'Choose event',
  },
  duplicateEventWarning: 'Duplicate event',
  duplicateEventSuggestion: 'Edit existing hook.',
  invalidActionWarning: 'A valid action is required.',
  matcherActions: {
    matcherSectionTitle: 'Matchers',
    matcherAdd: 'Add matcher',
    matcherPatternLabel: 'Pattern',
    matcherPatternPlaceholder: 'Pattern placeholder',
    matcherPatternHelp,
    matcherUnsupportedMessage: 'Matcher is unsupported.',
    matcherRemove: 'Remove matcher',
    executionSectionTitle: 'Executions',
    executionAdd: 'Add execution',
    executionTypeLabel: 'Action type',
    executionTimeoutLabel: 'Timeout',
    executionTimeoutPlaceholder: '600',
    executionTimeoutHelp: 'Timeout help',
    executionCommandLabel: 'Command',
    executionCommandPlaceholder: 'Command placeholder',
    executionCommandHelp: 'Command help',
    executionStatusMessageLabel: 'Status message',
    executionStatusMessagePlaceholder: 'Status placeholder',
    executionStatusMessageHelp: 'Status help',
    executionConditionLabel: 'Condition',
    executionConditionPlaceholder: 'Condition placeholder',
    executionConditionHelp: 'Condition help',
    executionAsyncLabel: 'Run asynchronously',
    executionAsyncRewakeLabel: 'Rewake after completion',
    executionShellLabel: 'Shell',
    executionShellPlaceholder: 'Select shell',
    executionShellHelp: 'Shell help',
    executionRemove: 'Remove execution',
  },
});

export const createHookDialogTestOptions = (): HookDialogOptions => ({
  events: [
    { value: 'SessionStart', label: 'SessionStart' },
    { value: 'PreToolUse', label: 'PreToolUse' },
    { value: 'Stop', label: 'Stop' },
  ],
  scopes: [
    { value: 'project', label: 'Project' },
    { value: 'user', label: 'User' },
    { value: 'local', label: 'Local' },
  ],
  executionTypes: HOOK_TYPES['claude-code'].map((hookType) => ({
    value: hookType,
    label: hookType,
  })),
  executionShells: [
    { value: 'bash', label: 'Bash' },
    { value: 'powershell', label: 'PowerShell' },
  ],
});
