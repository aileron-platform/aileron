import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { AUTHORIZATION_ERROR_CODES } from '@/shared/authorization/authorizationErrorCodes';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';
import { RESOURCE_ACCESS_ROLES } from '@/shared/authorization/resourceAccessRole';
import { RESOURCE_ACCESS_SOURCES } from '@/shared/authorization/resourceAuthorization';
import { PLATFORM_ROLES } from './platformRoles';

interface AuthorizationWireContract {
  schemaVersion: number;
  platformRoles: string[];
  resourceAccessRoles: string[];
  resourceAccessSources: string[];
  operationIds: string[];
  errorCodes: string[];
}

const contractPath = fs.existsSync('/contracts/authorization/wire-contract.json')
  ? '/contracts/authorization/wire-contract.json'
  : path.resolve(process.cwd(), '../contracts/authorization/wire-contract.json');

const contract = JSON.parse(
  fs.readFileSync(contractPath, 'utf8'),
) as AuthorizationWireContract;

describe('authorization wire contract', () => {
  it('keeps frontend authorization identifiers equal to the shared contract', () => {
    expect(contract.schemaVersion).toBe(2);
    expect([...PLATFORM_ROLES]).toEqual(contract.platformRoles);
    expect([...RESOURCE_ACCESS_ROLES]).toEqual(contract.resourceAccessRoles);
    expect([...RESOURCE_ACCESS_SOURCES]).toEqual(contract.resourceAccessSources);
    expect(Object.values(OPERATION_IDS)).toEqual(contract.operationIds);
    expect(Object.values(AUTHORIZATION_ERROR_CODES)).toEqual(contract.errorCodes);
  });
});
