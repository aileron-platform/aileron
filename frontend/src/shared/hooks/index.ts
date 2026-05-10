/**
 * Shared Hooks
 */

export { useContainerImages } from './useContainerImages';
export { useFormState, type UseFormStateReturn } from './useFormState';
export { useFormValidation, type UseFormValidationReturn, type ValidationRules } from './useFormValidation';
export { useI18n } from './useI18n';
export { useTaskProgress } from './useTaskProgress';
export {
  HOOK_DEFAULTS,
  HOOK_EVENTS,
  HOOK_EVENT_GROUPS,
  HOOK_EVENT_MATCHER_HINTS,
  HOOK_FIELD_SUPPORT,
  HOOK_TIMEOUT_DEFAULTS,
  HOOK_TYPES,
  HOOK_TYPE_FIELDS,
  createEmptyExecution,
  createEmptyHookValue,
  createEmptyMatcher,
  getHookDefaults,
  getHookFieldSupport,
  getHookTimeoutDefault,
  isValidEventForProvider,
  migrateActionToType,
  type HookDefaults,
  type HookEventValue,
  type HookEventMatcherHint,
  type HookFieldSupport,
  type HookTimeoutDefault,
  type HookType,
  type HookTypeFieldSupport,
} from './providerHookSpec';
