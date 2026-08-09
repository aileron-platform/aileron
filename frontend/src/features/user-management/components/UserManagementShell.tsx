import React from 'react';
import { Users, UsersRound, type LucideIcon } from 'lucide-react';
import {
  FeatureNavSidebarContent,
  ProductShell,
  type FeatureNavItem,
  type ProductShellBody,
  type ProductShellPreferencesAdapter,
} from '@/shared/components/shell';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  USER_MANAGEMENT_LAYOUT_ENTITY_ID,
  USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS,
  USER_MANAGEMENT_SHELL_LAYOUT_LIMITS,
  userManagementShellLayoutStorage,
} from '../storage/userManagementShellLayoutStorage';

export type UserManagementSection = 'users' | 'roleIssues' | 'disabledUsers' | 'groups' | 'emptyGroups' | 'groupMembers';

interface UserManagementShellProps {
  navigationSlot: React.ReactNode;
  activeSection: UserManagementSection;
  onSectionChange: (section: UserManagementSection) => void;
  usersCount: number;
  roleIssuesCount: number;
  groupsCount: number;
  main: React.ReactNode;
  detail?: React.ReactNode;
  detailTitle?: string;
  detailIcon?: LucideIcon;
  preferences?: ProductShellPreferencesAdapter;
}

const navigationItems: FeatureNavItem[] = [
  {
    id: 'users',
    icon: Users,
    labelKey: 'userManagement.navigation.users',
  },
  {
    id: 'groups',
    icon: UsersRound,
    labelKey: 'userManagement.navigation.groups',
  },
];

const resolveActiveId = (activeSection: UserManagementSection): 'users' | 'groups' => {
  if (activeSection === 'groups' || activeSection === 'emptyGroups' || activeSection === 'groupMembers') {
    return 'groups';
  }
  return 'users';
};

const UserManagementShellContent: React.FC<UserManagementShellProps> = ({
  navigationSlot,
  activeSection,
  onSectionChange,
  usersCount,
  roleIssuesCount,
  groupsCount,
  main,
  detail,
  detailTitle,
  detailIcon: DetailIcon = Users,
  preferences,
}) => {
  const { t } = useI18n();
  const activeId = resolveActiveId(activeSection);
  const items = navigationItems.map(item => ({
    ...item,
    count: item.id === 'users'
      ? usersCount
      : groupsCount,
  }));

  const body: ProductShellBody = {
    kind: 'regions',
    navigation: {
      content: ({ collapsed }) => (
        <FeatureNavSidebarContent
          testId="user-management-sidebar"
          items={items}
          activeId={activeId}
          collapsed={collapsed}
          showHeader={false}
          onSelect={(itemId) => {
            onSectionChange(itemId === 'groups' ? 'groups' : 'users');
          }}
          footer={(
            <div className="space-y-1.5 rounded-md bg-muted/60 px-2 py-1.5 text-xs text-muted-foreground">
              <div className="truncate font-medium text-foreground">
                {t('userManagement.navigation.statusSummary')}
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{t('userManagement.navigation.users')}</span>
                <span className="font-medium text-foreground">{usersCount}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{t('userManagement.navigation.groups')}</span>
                <span className="font-medium text-foreground">{groupsCount}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{t('userManagement.navigation.pendingIssues')}</span>
                <span className="font-medium text-foreground">{roleIssuesCount}</span>
              </div>
            </div>
          )}
        />
      ),
      behavior: {
        collapsible: true,
        resizable: true,
        defaultWidth: USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.navSidebarWidth,
        minWidth: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS.navSidebarWidth.min,
        maxWidth: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS.navSidebarWidth.max,
      },
      presentation: {
        accessibleLabel: t('userManagement.navigation.title'),
        chrome: 'navigation',
        responsive: 'always',
        header: {
          leading: <UsersRound className="h-4 w-4 shrink-0 text-sidebar-primary" aria-hidden="true" />,
          title: <span className="truncate text-sm font-medium text-sidebar-foreground">{t('userManagement.navigation.title')}</span>,
        },
      },
    },
    main: {
      accessibleLabel: t('userManagement.navigation.mainLabel'),
      content: <div data-testid="user-management-main" className="min-w-0 flex-1 overflow-hidden bg-background">{main}</div>,
    },
    ...(detail && detailTitle ? {
      companion: {
        content: () => <div data-testid="user-management-detail" className="min-h-0 flex-1 overflow-y-auto">{detail}</div>,
        placement: 'side' as const,
        side: {
          collapsible: true,
          resizable: true,
          defaultWidth: USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.companionWidth,
          minWidth: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS.companionWidth.min,
          maxWidth: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS.companionWidth.max,
        },
        bottom: {
          defaultHeight: USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.companionHeight,
          minHeight: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS.companionHeight.min,
          maxHeight: USER_MANAGEMENT_SHELL_LAYOUT_LIMITS.companionHeight.max,
          mainMinHeight: 320,
        },
        presentation: {
          accessibleLabel: detailTitle,
          chrome: 'muted-rail' as const,
          header: {
            leading: <DetailIcon className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />,
            title: <span className="truncate text-sm font-medium">{detailTitle}</span>,
          },
          collapsedContent: <DetailIcon className="h-4 w-4 text-primary" aria-hidden="true" data-testid="user-management-detail-collapsed-icon" />,
          collapseLabel: t('shared.shell.collapseSidebar'),
          expandLabel: t('shared.shell.expandSidebar'),
          resizeLabel: t('shared.shell.resizeSidebar'),
        },
      },
    } : {}),
  };

  return <ProductShell topBar={navigationSlot} body={body} preferences={preferences} />;
};

export const UserManagementShell: React.FC<UserManagementShellProps> = (props) => {
  const preferences = React.useMemo<ProductShellPreferencesAdapter>(() => ({
    identity: `user-management:${USER_MANAGEMENT_LAYOUT_ENTITY_ID}`,
    load: () => {
      const stored = userManagementShellLayoutStorage.load(USER_MANAGEMENT_LAYOUT_ENTITY_ID);
      return stored ? {
        navigation: { collapsed: stored.navSidebarCollapsed, width: stored.navSidebarWidth },
        companion: {
          collapsed: stored.companionCollapsed,
          width: stored.companionWidth,
          height: stored.companionHeight,
          placement: stored.companionPlacement,
        },
      } : null;
    },
    save: (stored) => {
      userManagementShellLayoutStorage.save(USER_MANAGEMENT_LAYOUT_ENTITY_ID, {
        ...USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS,
        navSidebarCollapsed: stored.navigation?.collapsed ?? USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.navSidebarCollapsed,
        navSidebarWidth: stored.navigation?.width ?? USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.navSidebarWidth,
        companionCollapsed: stored.companion?.collapsed ?? USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.companionCollapsed,
        companionWidth: stored.companion?.width ?? USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.companionWidth,
        companionHeight: stored.companion?.height ?? USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.companionHeight,
        companionPlacement: stored.companion?.placement ?? USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS.companionPlacement,
      });
    },
  }), []);

  return <UserManagementShellContent {...props} preferences={preferences} />;
};
