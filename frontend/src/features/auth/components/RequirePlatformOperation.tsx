import React from 'react';
import type { OperationId } from '@/shared/authorization/operationIds';
import { useAuth } from '../hooks/useAuth';
import { AuthorizationDeniedState } from './AuthorizationDeniedState';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import { projectPlatformIdentityEntry } from '@/shared/components/entry/platformIdentityEntryProjection';

interface RequirePlatformOperationProps {
  children: React.ReactNode;
  operationId: OperationId;
  navigationSlot?: React.ReactNode;
}

const identityCheckingProjection = projectPlatformIdentityEntry({ status: 'checking' });
const identityResolvedProjection = projectPlatformIdentityEntry({ status: 'authenticated' });

export const RequirePlatformOperation: React.FC<RequirePlatformOperationProps> = ({
  children,
  operationId,
  navigationSlot,
}) => {
  const { hasPlatformOperation, isLoading } = useAuth();

  if (isLoading) {
    return (
      <EntryFrame
        isPending
        transitionKey="platform-identity"
        projection={identityCheckingProjection}
        navigationSlot={navigationSlot}
        onAction={() => undefined}
      >
        {null}
      </EntryFrame>
    );
  }

  if (!hasPlatformOperation(operationId)) {
    return (
      <EntryFrame
        isPending={false}
        keepFrame
        transitionKey="platform-identity"
        projection={identityResolvedProjection}
        navigationSlot={navigationSlot}
        onAction={() => undefined}
      >
        <AuthorizationDeniedState />
      </EntryFrame>
    );
  }

  return children;
};
