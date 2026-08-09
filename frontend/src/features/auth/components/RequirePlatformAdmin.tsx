import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { AuthorizationDeniedState } from './AuthorizationDeniedState';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import { projectPlatformIdentityEntry } from '@/shared/components/entry/platformIdentityEntryProjection';

interface RequirePlatformAdminProps {
  children: React.ReactNode;
  navigationSlot?: React.ReactNode;
}

const identityCheckingProjection = projectPlatformIdentityEntry({ status: 'checking' });
const identityResolvedProjection = projectPlatformIdentityEntry({ status: 'authenticated' });

export const RequirePlatformAdmin: React.FC<RequirePlatformAdminProps> = ({
  children,
  navigationSlot,
}) => {
  const { isPlatformAdmin, isLoading } = useAuth();

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

  if (!isPlatformAdmin) {
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
