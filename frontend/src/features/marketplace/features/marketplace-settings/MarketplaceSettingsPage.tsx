import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Clock3,
  FileDiff,
  GitBranch,
  History,
  KeyRound,
  Settings,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { FeatureNavSidebarContent, type FeatureNavItem } from '@/shared/components/shell';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { apiClient } from '@/shared/api/apiClient';
import type { VersionControlRepositoryStatus } from '@/shared/version-control';
import type { VersionControlWorkbenchMode } from '@/shared/components/version-control';
import type {
  UserSettings,
  UserSettingsResponse,
  UserSettingsSSH,
} from '@/shared/types/user';
import {
  getRegistrySettings,
  saveRegistrySettings,
} from '../../api/marketplaceApi';
import { MarketplaceActivityTab } from './components/MarketplaceActivityTab';
import { MarketplaceGeneralTab, type MarketplaceRootMetadata } from './components/MarketplaceGeneralTab';
import { MarketplaceSshKeysTab } from './components/MarketplaceSshKeysTab';
import {
  MarketplaceVersionControlTab,
  type MarketplaceVersionControlRenderSurface,
} from './components/MarketplaceVersionControlTab';
import { useAuth } from '@/features/auth/public';
import { MarketplaceShellAdapter } from '../../components/MarketplaceShellAdapter';

export interface MarketplaceSettingsPageProps {
  userId: string | null;
  navigationSlot?: React.ReactNode;
}

export type MarketplaceSettingsSection = 'general' | 'versionControl' | 'sshKeys' | 'activity';
export type MarketplaceVersionControlSubmenu = VersionControlWorkbenchMode;

interface MarketplaceSettingsNavigationRenderState {
  collapsed: boolean;
}

const MARKETPLACE_SETTINGS_SECTIONS = new Set<MarketplaceSettingsSection>([
  'general',
  'versionControl',
  'sshKeys',
  'activity',
]);

const isMarketplaceSettingsSection = (value: string | null): value is MarketplaceSettingsSection => (
  value !== null && MARKETPLACE_SETTINGS_SECTIONS.has(value as MarketplaceSettingsSection)
);

const isMarketplaceVersionControlSubmenu = (
  value: string | null,
): value is MarketplaceVersionControlSubmenu => (
  value === 'changes' || value === 'history'
);

interface MarketplaceSettingsNavigationProps {
  activeSection: MarketplaceSettingsSection;
  activeVersionControlSubmenu: MarketplaceVersionControlSubmenu;
  canManageRegistry: boolean;
  onSelect: (section: MarketplaceSettingsSection) => void;
  onSelectSubmenu: (submenu: MarketplaceVersionControlSubmenu) => void;
  collapsed?: boolean;
}

/**
 * Settings navigation content. ProductShell owns the navigation geometry;
 * this component only exposes translated labels, icons, and selection state.
 */
export const MarketplaceSettingsNavigation: React.FC<MarketplaceSettingsNavigationProps> = ({
  activeSection,
  activeVersionControlSubmenu,
  canManageRegistry,
  onSelect,
  onSelectSubmenu,
  collapsed = false,
}) => {
  const items: FeatureNavItem[] = [
    ...(canManageRegistry ? [
      { id: 'general', labelKey: 'marketplace.settings.sections.general', icon: Settings },
      {
        id: 'versionControl',
        labelKey: 'marketplace.settings.sections.versionControl',
        icon: GitBranch,
        subItems: [
          {
            id: 'changes',
            labelKey: 'shared.versionControl.mode.fileChanges',
            icon: FileDiff,
          },
          {
            id: 'history',
            labelKey: 'shared.versionControl.mode.commitHistory',
            icon: History,
          },
        ],
      },
    ] : []),
    { id: 'sshKeys', labelKey: 'marketplace.settings.sections.sshKeys', icon: KeyRound },
    { id: 'activity', labelKey: 'marketplace.settings.sections.activity', icon: Clock3 },
  ];

  return (
    <FeatureNavSidebarContent
      testId="marketplace-settings-navigation"
      items={items}
      activeId={activeSection}
      activeSubId={activeSection === 'versionControl' ? activeVersionControlSubmenu : null}
      onSelect={(section) => {
        if (isMarketplaceSettingsSection(section)) {
          onSelect(section);
        }
      }}
      onSelectSub={(section, submenu) => {
        if (section === 'versionControl' && isMarketplaceVersionControlSubmenu(submenu)) {
          onSelectSubmenu(submenu);
        }
      }}
      collapsed={collapsed}
      showHeader={false}
    />
  );
};

export const MarketplaceSettingsPage: React.FC<MarketplaceSettingsPageProps> = ({ userId, navigationSlot }) => {
  const { t } = useI18n();
  const { isPlatformAdmin } = useAuth();
  const canManageRegistry = isPlatformAdmin;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSection = searchParams.get('section');
  const requestedLegacySection = searchParams.get('tab');
  const sectionCandidate = requestedSection ?? requestedLegacySection;
  const canAccessSection = React.useCallback((section: string): boolean => {
    if (section === 'general' || section === 'versionControl') {
      return canManageRegistry;
    }
    return section === 'sshKeys' || section === 'activity';
  }, [canManageRegistry]);
  const fallbackSection = canManageRegistry
    ? 'general'
    : 'activity';
  const activeSection = sectionCandidate
    && isMarketplaceSettingsSection(sectionCandidate)
    && canAccessSection(sectionCandidate)
    ? sectionCandidate
    : fallbackSection;
  const requestedVersionControlSubmenu = searchParams.get('submenu')
    ?? (requestedSection === null && requestedLegacySection === 'versionControl'
      ? searchParams.get('mode')
      : null);
  const activeVersionControlSubmenu: MarketplaceVersionControlSubmenu = activeSection === 'versionControl'
    && isMarketplaceVersionControlSubmenu(requestedVersionControlSubmenu)
    ? requestedVersionControlSubmenu
    : 'changes';
  const [userSettings, setUserSettings] = React.useState<UserSettings | null>(null);
  const [sshKeys, setSshKeys] = React.useState<UserSettingsSSH>({
    publicKey: null,
    privateKey: null,
    fingerprint: null,
    lastRotatedAt: null,
  });
  const [showPrivateKey, setShowPrivateKey] = React.useState(false);
  const [registryRepository, setRegistryRepository] = React.useState<VersionControlRepositoryStatus | null>(null);
  const [registryRootPath, setRegistryRootPath] = React.useState('');
  const [rootMetadata, setRootMetadata] = React.useState<MarketplaceRootMetadata>({
    name: '',
    maintainerName: '',
    maintainerEmail: '',
    description: '',
  });
  const [isSavingGeneral, setIsSavingGeneral] = React.useState(false);

  React.useEffect(() => {
    if (!canManageRegistry) {
      return undefined;
    }

    let isActive = true;
    void getRegistrySettings().then(settings => {
      if (!isActive) return;
      setRegistryRootPath(settings.rootPath);
      setRootMetadata({
        name: settings.displayName,
        maintainerName: settings.maintainerName,
        maintainerEmail: settings.maintainerEmail,
        description: settings.description ?? '',
      });
    });
    return () => {
      isActive = false;
    };
  }, [canManageRegistry]);

  React.useEffect(() => {
    if (!userId) return;
    let isActive = true;
    void apiClient.get<UserSettingsResponse>(`/users/${userId}/settings`).then(response => {
      if (!isActive) return;
      setUserSettings(response.data);
      setSshKeys(response.data.ssh);
    });
    return () => {
      isActive = false;
    };
  }, [userId]);

  const handleSaveGeneral = async () => {
    if (!canManageRegistry) return;
    setIsSavingGeneral(true);
    try {
      const result = await saveRegistrySettings({
        name: rootMetadata.name,
        owner: {
          name: rootMetadata.maintainerName,
          email: rootMetadata.maintainerEmail,
        },
        description: rootMetadata.description,
      });
      setRegistryRootPath(result.settings.rootPath);
      setRootMetadata({
        name: result.settings.displayName,
        maintainerName: result.settings.maintainerName,
        maintainerEmail: result.settings.maintainerEmail,
        description: result.settings.description ?? '',
      });
    } finally {
      setIsSavingGeneral(false);
    }
  };

  const handleSaveSshKeys = async () => {
    if (!userId || !userSettings) return;
    const response = await apiClient.put<UserSettingsResponse>(`/users/${userId}/settings`, {
      ...userSettings,
      ssh: sshKeys,
    });
    setUserSettings(response.data);
    setSshKeys(response.data.ssh);
  };

  const handleGenerateSshKey = async () => {
    if (!userId) return;
    const response = await apiClient.post<{
      publicKey: string;
      privateKey: string;
      fingerprint: string;
      generatedAt: string;
    }>(`/users/${userId}/ssh-keys/generate`);
    const nextSshKeys = {
      publicKey: response.publicKey,
      privateKey: response.privateKey,
      fingerprint: response.fingerprint,
      lastRotatedAt: response.generatedAt,
    };
    setSshKeys(nextSshKeys);
    setUserSettings(previous => previous ? { ...previous, ssh: nextSshKeys } : previous);
  };

  const copyToClipboard = (value: string | null) => {
    if (!value) return;
    void navigator.clipboard?.writeText(value);
  };

  const handleRepositoryChange = React.useCallback((repository: VersionControlRepositoryStatus) => {
    setRegistryRepository(repository);
  }, []);

  const setActiveSection = React.useCallback((section: MarketplaceSettingsSection) => {
    if (!canAccessSection(section)) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set('section', section);
    next.delete('submenu');
    next.delete('mode');
    next.delete('page');
    if (section === 'versionControl') {
      next.set('submenu', 'changes');
    }
    setSearchParams(next);
  }, [canAccessSection, searchParams, setSearchParams]);

  const setVersionControlSubmenu = React.useCallback((submenu: MarketplaceVersionControlSubmenu) => {
    const next = new URLSearchParams(searchParams);
    next.set('section', 'versionControl');
    next.set('submenu', submenu);
    next.delete('mode');
    next.delete('page');
    setSearchParams(next);
  }, [searchParams, setSearchParams]);

  React.useEffect(() => {
    const next = new URLSearchParams(searchParams);
    let changed = false;
    if (next.get('section') !== activeSection) {
      next.set('section', activeSection);
      changed = true;
    }
    if (activeSection === 'versionControl') {
      if (next.get('submenu') !== activeVersionControlSubmenu) {
        next.set('submenu', activeVersionControlSubmenu);
        changed = true;
      }
    } else if (next.has('submenu')) {
      next.delete('submenu');
      changed = true;
    }
    if (next.has('tab')) {
      next.delete('tab');
      changed = true;
    }
    if (next.has('mode')) {
      next.delete('mode');
      changed = true;
    }
    if (changed) {
      setSearchParams(next, { replace: true });
    }
  }, [activeSection, activeVersionControlSubmenu, searchParams, setSearchParams]);

  const renderSettingsMain = React.useCallback(() => {
    if (canManageRegistry && activeSection === 'general') {
      return (
        <div className="h-full overflow-auto">
          <div className="mx-auto w-full max-w-7xl p-6">
            <MarketplaceGeneralTab
              metadata={rootMetadata}
              rootPath={registryRootPath}
              isSaving={isSavingGeneral}
              onMetadataChange={setRootMetadata}
              onSave={() => void handleSaveGeneral()}
            />
          </div>
        </div>
      );
    }

    if (activeSection === 'sshKeys') {
      return (
        <div className="h-full overflow-auto">
          <div className="mx-auto w-full max-w-7xl p-6">
            <MarketplaceSshKeysTab
              sshKeys={sshKeys}
              showPrivateKey={showPrivateKey}
              onSshKeysChange={setSshKeys}
              onShowPrivateKeyChange={setShowPrivateKey}
              onGenerateSshKey={() => void handleGenerateSshKey()}
              onSaveSshKeys={() => void handleSaveSshKeys()}
              onCopy={copyToClipboard}
            />
          </div>
        </div>
      );
    }

    return (
      <div className="h-full overflow-auto">
        <div className="mx-auto w-full max-w-7xl p-6">
          <MarketplaceActivityTab />
        </div>
      </div>
    );
  }, [
    activeSection,
    canManageRegistry,
    copyToClipboard,
    handleGenerateSshKey,
    handleSaveGeneral,
    handleSaveSshKeys,
    isSavingGeneral,
    registryRootPath,
    rootMetadata,
    setRootMetadata,
    showPrivateKey,
    sshKeys,
  ]);

  const settingsHeader = (
    <FeatureHeader
      title={t('marketplace.settings.title')}
      icon={Settings}
      breadcrumbs={[t('marketplace.breadcrumbs.root')]}
      info={(
        <div className="text-xs text-muted-foreground">
          {t('marketplace.settings.description')}
        </div>
      )}
      actions={(
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate(ROUTES.marketplace.packages)}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.common.actions.back')}
          </Button>
        </div>
      )}
      className="h-full w-full border-0"
    />
  );

  const settingsNavigation = {
    content: ({ collapsed }: MarketplaceSettingsNavigationRenderState) => (
      <MarketplaceSettingsNavigation
        activeSection={activeSection}
        activeVersionControlSubmenu={activeVersionControlSubmenu}
        canManageRegistry={canManageRegistry}
        onSelect={setActiveSection}
        onSelectSubmenu={setVersionControlSubmenu}
        collapsed={collapsed}
      />
    ),
    accessibleLabel: t('marketplace.settings.navigation.label'),
    preset: 'settings-navigation' as const,
    title: t('marketplace.settings.title'),
    icon: Settings,
  };

  const renderVersionControlSurface = React.useCallback((
    surface: MarketplaceVersionControlRenderSurface,
  ) => {
    if (surface.kind === 'state') {
      return (
        <MarketplaceShellAdapter
          navigationSlot={navigationSlot}
          surface={{
            kind: 'settings',
            header: settingsHeader,
            navigation: settingsNavigation,
            main: {
              accessibleLabel: t('marketplace.settings.main.label'),
              content: surface.content,
            },
          }}
        />
      );
    }

    const navigatorRegion = {
      content: ({ collapsed }: MarketplaceSettingsNavigationRenderState) => (
        collapsed ? null : surface.navigator
      ),
      accessibleLabel: t('marketplace.settings.versionControl.title'),
      preset: 'settings-navigator' as const,
      title: t('marketplace.settings.versionControl.title'),
      icon: activeVersionControlSubmenu === 'changes' ? FileDiff : History,
      actions: surface.navigatorActions,
    };

    return (
      <MarketplaceShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'settings',
          header: settingsHeader,
          navigation: settingsNavigation,
          navigator: navigatorRegion,
          main: {
            accessibleLabel: t('marketplace.settings.main.label'),
            content: <>{surface.main}{surface.dialogs}</>,
          },
        }}
      />
    );
  }, [activeVersionControlSubmenu, navigationSlot, settingsHeader, settingsNavigation, t]);

  if (canManageRegistry && activeSection === 'versionControl') {
    return (
      <MarketplaceVersionControlTab
        repository={registryRepository}
        onRepositoryChange={handleRepositoryChange}
        mode={activeVersionControlSubmenu}
        renderSurface={renderVersionControlSurface}
      />
    );
  }

  return (
    <MarketplaceShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'settings',
        header: settingsHeader,
        navigation: settingsNavigation,
        main: {
          accessibleLabel: t('marketplace.settings.main.label'),
          content: renderSettingsMain(),
        },
      }}
    />
  );
};
