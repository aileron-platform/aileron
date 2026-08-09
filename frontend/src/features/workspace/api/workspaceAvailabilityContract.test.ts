import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  WORKSPACE_AVAILABILITY_ACTIONS,
  WORKSPACE_AVAILABILITY_REASON_CODES,
  WORKSPACE_AVAILABILITY_STATES,
  WORKSPACE_DELETION_ACTIONS,
  WORKSPACE_DELETION_PHASES,
  WORKSPACE_KNOWLEDGE_MOUNT_STATES,
} from './workspaceLifecycleApi';

interface WorkspaceAvailabilityContract {
  availabilityStates: string[];
  allowedActions: string[];
  knowledgeMountStates: string[];
  deletionProjection: {
    phases: string[];
    actions: string[];
  };
  reasonCodes: Record<string, {
    availability: string;
    defaultAllowedActions: string[];
  }>;
}

const resolveContractPath = (): string => {
  const candidates = [
    '/contracts/workspace-availability.json',
    path.resolve(process.cwd(), '../contracts/workspace-availability.json'),
  ];
  const contractPath = candidates.find((candidate) => fs.existsSync(candidate));
  if (!contractPath) {
    throw new Error('workspace availability contract is not mounted');
  }
  return contractPath;
};

const contract = JSON.parse(
  fs.readFileSync(resolveContractPath(), 'utf8'),
) as WorkspaceAvailabilityContract;

describe('workspace availability frontend contract', () => {
  it('keeps availability states, actions, mount states, and reason codes aligned', () => {
    expect([...WORKSPACE_AVAILABILITY_STATES]).toEqual(contract.availabilityStates);
    expect([...WORKSPACE_AVAILABILITY_ACTIONS]).toEqual(contract.allowedActions);
    expect([...WORKSPACE_KNOWLEDGE_MOUNT_STATES]).toEqual(contract.knowledgeMountStates);
    expect([...WORKSPACE_DELETION_PHASES]).toEqual(contract.deletionProjection.phases);
    expect([...WORKSPACE_DELETION_ACTIONS]).toEqual(contract.deletionProjection.actions);
    expect([...WORKSPACE_AVAILABILITY_REASON_CODES].sort()).toEqual(
      Object.keys(contract.reasonCodes).sort(),
    );
  });

  it('keeps every reason definition inside the frontend state and action domains', () => {
    const states = new Set<string>(WORKSPACE_AVAILABILITY_STATES);
    const actions = new Set<string>(WORKSPACE_AVAILABILITY_ACTIONS);

    for (const definition of Object.values(contract.reasonCodes)) {
      expect(states.has(definition.availability)).toBe(true);
      expect(definition.defaultAllowedActions.every((action) => actions.has(action))).toBe(true);
    }
  });
});
