import type { VersionControlActionMenuItem } from './VersionControlActionMenu';

type ActionId = VersionControlActionMenuItem['id'];

interface VersionControlActionDefinition {
  onClick: () => void;
  disabled?: boolean;
  disabledReasonKey?: string;
  labelKey?: string;
}

type VersionControlActionDefinitions = Partial<Record<ActionId, VersionControlActionDefinition>>;

const actionOrder: readonly ActionId[] = [
  'refresh',
  'fetch',
  'pull',
  'push',
  'remoteSettings',
  'lfs',
];

export const createVersionControlActionItems = (
  definitions: VersionControlActionDefinitions,
): VersionControlActionMenuItem[] => actionOrder.flatMap(id => {
  const definition = definitions[id];
  return definition ? [{ id, ...definition }] : [];
});
