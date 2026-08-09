import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AdminUser } from '../api/userManagementTypes';

interface RoleIssueBadgeProps {
  user: AdminUser;
}

export const RoleIssueBadge: React.FC<RoleIssueBadgeProps> = ({ user }) => {
  const { t } = useI18n();
  if (user.roleStatus === 'valid') {
    return null;
  }

  return (
    <Badge variant="outline" className="gap-1 border-amber-500/30 bg-amber-500/10 text-amber-700">
      <AlertTriangle className="h-3 w-3" />
      {t(`userManagement.roleIssues.${user.roleStatus}`)}
    </Badge>
  );
};
