import React from 'react';
import { ShieldCheck } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AdminUser, PlatformRole } from '../api/userManagementTypes';
import { PLATFORM_ROLES } from '../model/userManagementUserModel';
import { RoleIssueBadge } from './RoleIssueBadge';

interface UserDetailPanelProps {
  user: AdminUser;
  onAssignRole: (userId: string, role: PlatformRole) => Promise<void>;
}

const displayValue = (value: string | null, unavailable: string): string => value ?? unavailable;

export const UserDetailPanel: React.FC<UserDetailPanelProps> = ({
  user,
  onAssignRole,
}) => {
  const { t } = useI18n();
  const [assignRoleOpen, setAssignRoleOpen] = React.useState(false);
  const [selectedRole, setSelectedRole] = React.useState<PlatformRole>(
    user.role ?? 'member',
  );
  const localActiveLabel = user.localActive ? t('userManagement.values.yes') : t('userManagement.values.no');
  const identityEnabledLabel = user.identityEnabled
    ? t('userManagement.values.yes')
    : t('userManagement.values.no');
  const unavailable = t('userManagement.values.notAvailable');

  React.useEffect(() => {
    setSelectedRole(user.role ?? 'member');
  }, [user.id, user.role]);

  const submitRoleAssignment = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await onAssignRole(user.id, selectedRole);
      setAssignRoleOpen(false);
    } catch {
      // The page reports the localized API error.
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="border-b bg-card px-4 py-3">
        <div className="truncate text-xs text-muted-foreground">{user.email ?? user.username}</div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge variant={user.enabled ? 'default' : 'outline'}>
            {t(`userManagement.users.accountState.${user.accountState}`)}
          </Badge>
          <Badge variant="secondary">
            {user.role ? t(`userManagement.roles.${user.role}`) : t('userManagement.roles.none')}
          </Badge>
          {user.roleStatus === 'valid' ? (
            <Badge variant="outline">{t('userManagement.roleIssues.valid')}</Badge>
          ) : null}
          <RoleIssueBadge user={user} />
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <div className="rounded-md border border-border bg-background px-3 py-2">
          <div className="text-xs font-medium text-muted-foreground">{t('userManagement.users.fields.username')}</div>
          <div className="mt-1 truncate text-sm font-medium text-foreground">{user.username}</div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div
            data-testid="user-detail-local-status"
            className="rounded-md border border-border bg-muted/30 px-3 py-2"
          >
            <div className="text-xs font-medium text-muted-foreground">{t('userManagement.users.fields.localActive')}</div>
            <div className="mt-1 text-sm font-medium text-foreground">{localActiveLabel}</div>
          </div>
          <div
            data-testid="user-detail-identity-status"
            className="rounded-md border border-border bg-muted/30 px-3 py-2"
          >
            <div className="text-xs font-medium text-muted-foreground">{t('userManagement.users.fields.identityEnabled')}</div>
            <div className="mt-1 text-sm font-medium text-foreground">{identityEnabledLabel}</div>
          </div>
        </div>
        <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
          <div className="text-xs font-medium text-muted-foreground">{t('userManagement.users.fields.issuer')}</div>
          <div className="mt-1 break-words text-sm font-medium text-foreground">
            {displayValue(user.issuer, unavailable)}
          </div>
        </div>
        <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
          <div className="text-xs font-medium text-muted-foreground">{t('userManagement.users.fields.subject')}</div>
          <div className="mt-1 break-words text-sm font-medium text-foreground">
            {displayValue(user.subject, unavailable)}
          </div>
        </div>
      </div>

      <div className="space-y-2 border-t bg-card p-4">
        <Button
          type="button"
          size="sm"
          className="h-8 w-full justify-start gap-2 px-2 text-xs"
          variant="outline"
          onClick={() => setAssignRoleOpen(true)}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          {t('userManagement.users.actions.assignRole')}
        </Button>
      </div>

      <Dialog open={assignRoleOpen} onOpenChange={setAssignRoleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogHeading icon={ShieldCheck}>
              {t('userManagement.users.assignRoleDialog.title')}
            </DialogHeading>
            <DialogDescription>{t('userManagement.users.assignRoleDialog.description')}</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={submitRoleAssignment}>
            <div className="space-y-2">
              <Label htmlFor="user-management-assign-role">
                {t('userManagement.users.assignRoleDialog.fields.role')}
              </Label>
              <select
                id="user-management-assign-role"
                value={selectedRole}
                onChange={event => setSelectedRole(event.target.value as PlatformRole)}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {PLATFORM_ROLES.map(role => (
                  <option key={role} value={role}>
                    {t(`userManagement.roles.${role}`)}
                  </option>
                ))}
              </select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAssignRoleOpen(false)}>
                {t('userManagement.users.assignRoleDialog.actions.cancel')}
              </Button>
              <Button type="submit">
                {t('userManagement.users.assignRoleDialog.actions.save')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
};
