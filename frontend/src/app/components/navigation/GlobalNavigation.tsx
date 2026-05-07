import React from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('GlobalNavigation');
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { apiClient } from '@/shared/api/apiClient';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
} from '@/shared/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/shared/components/ui/avatar';
import {
  Folder,
  ChevronDown,
  FolderPlus,
  User,
  Clock,
  Store,
  Library,
  Settings,
  LogOut,
  LogIn,
  Maximize,
  Minimize,
} from 'lucide-react';
import { useNavigation, ModuleType } from '@/app/providers/NavigationProvider';
import { useI18n } from '@/app/providers/I18nProvider';
import { useAuth } from '@/features/auth/hooks/useAuth';
import type { OidcUserProfile } from '@/features/auth/types';
import { useApp } from '@/app/providers/AppProvider';
import { cn } from '@/shared/utils/cn';
import { validateUserSettings } from '@/shared/services/userSettingsValidation';
import { SettingsCheckDialog } from '@/app/components/dialogs/SettingsCheckDialog';
import type { UserSettings, UserSettingsResponse } from '@/shared/types/user';
import type { SettingsValidationResult } from '@/shared/services/userSettingsValidation';
import { ROUTES } from '@/shared/constants/routes';
import { useToast } from '@/shared/components/ui/use-toast';

interface WorkspaceOwner {
  id: string;
  displayName: string;
  avatarUrl?: string | null;
}

interface WorkspaceSummary {
  id: string;
  name: string;
  description?: string | null;
  owner?: WorkspaceOwner;
  provisioner?: 'docker' | 'kubernetes';
  targetNamespace?: string | null;
  overallPhase?: string | null;
  runtime?: string | null;
  runtimeStatus?: string | null;
}

interface WorkspaceListResponse {
  items?: WorkspaceSummary[];
}

export const GlobalNavigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, dispatch } = useNavigation();
  const { t } = useI18n();
  const { logout, user, isAuthenticated } = useAuth();
  const { state: appState } = useApp();
  const { toast } = useToast();

  const [workspaces, setWorkspaces] = React.useState<WorkspaceSummary[]>([]);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = React.useState<boolean>(false);
  const [hasWorkspaceError, setHasWorkspaceError] = React.useState<boolean>(false);

  const [showSettingsCheckDialog, setShowSettingsCheckDialog] = React.useState<boolean>(false);
  const [validationResult, setValidationResult] = React.useState<SettingsValidationResult | null>(null);

  const userDisplayName = React.useMemo(() => {
    if (!user) return t('navigation.userMenu.defaultUser');
    const oidcUser = user as OidcUserProfile;
    return oidcUser.preferred_username || oidcUser.email || oidcUser.sub || t('navigation.userMenu.defaultUser');
  }, [t, user]);

  const userEmail = React.useMemo(() => {
    if (!user) return '';
    return (user as OidcUserProfile).email || '';
  }, [user]);

  const userInitials = React.useMemo(() => {
    const name = userDisplayName || 'U';
    const words = name.trim().split(/\s+/);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  }, [userDisplayName]);

  const [isFullscreen, setIsFullscreen] = React.useState<boolean>(() => !!document.fullscreenElement);

  React.useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('navigation.fullscreen.error'),
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const selectedWorkspace = React.useMemo(() => {
    return workspaces.find(workspace => workspace.id === state.selectedWorkspaceId) ?? null;
  }, [state.selectedWorkspaceId, workspaces]);

  const getProvisionerLabel = React.useCallback(
    (provisioner?: WorkspaceSummary['provisioner']) => {
      if (provisioner === 'kubernetes') {
        return t('navigation.workspaceSelector.provisioners.kubernetes');
      }
      return t('navigation.workspaceSelector.provisioners.docker');
    },
    [t]
  );

  const getPhaseLabel = React.useCallback(
    (phase?: string | null) => {
      if (!phase) {
        return t('navigation.workspaceSelector.phases.unknown');
      }
      const phaseKey = phase.toLowerCase();
      const localized = t(`navigation.workspaceSelector.phases.${phaseKey}`);
      return localized === `navigation.workspaceSelector.phases.${phaseKey}` ? phase : localized;
    },
    [t]
  );

  const getPhaseBadgeClassName = React.useCallback((phase?: string | null) => {
    switch (phase?.toLowerCase()) {
      case 'running':
        return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700';
      case 'starting':
      case 'reconciling':
      case 'pending':
        return 'border-amber-500/20 bg-amber-500/10 text-amber-700';
      case 'failed':
      case 'error':
        return 'border-destructive/20 bg-destructive/10 text-destructive';
      case 'disabled':
      case 'stopped':
        return 'border-slate-500/20 bg-slate-500/10 text-slate-700';
      default:
        return 'border-primary/20 bg-primary/10 text-primary';
    }
  }, []);

  const setActiveModule = (module: ModuleType) => {
    dispatch({ type: 'SET_CURRENT_MODULE', payload: module });
    switch (module) {
      case 'workspace':
        navigate(ROUTES.WORKSPACES);
        break;
      case 'marketplace':
        navigate(ROUTES.MARKETPLACE);
        break;
      case 'automation':
        navigate(ROUTES.AUTOMATION);
        break;
      case 'knowledge-base':
        navigate(ROUTES.KNOWLEDGE_BASES);
        break;
      default:
        navigate(ROUTES.WORKSPACES);
    }
  };

  React.useEffect(() => {
    const controller = new AbortController();
    let isActive = true;

    const fetchWorkspaces = async () => {
      setIsLoadingWorkspaces(true);
      setHasWorkspaceError(false);

      try {
        const data = await apiClient.get<WorkspaceListResponse>('/workspaces/?page=1&pageSize=50');
        if (!isActive) {
          return;
        }

        const items = Array.isArray(data?.items) ? data.items : [];
        setWorkspaces(items);
        const currentSelected = state.selectedWorkspaceId;
        if (currentSelected && items.some(item => item.id === currentSelected)) {
          return;
        }
        const newSelectedId = items.length > 0 ? items[0].id : null;
        dispatch({ type: 'SET_SELECTED_WORKSPACE', payload: newSelectedId });
      } catch (error) {
        if (!isActive || controller.signal.aborted) {
          return;
        }
        logger.error('Failed to load workspaces', { error });
        setHasWorkspaceError(true);
        setWorkspaces([]);
        dispatch({ type: 'SET_SELECTED_WORKSPACE', payload: null });
      } finally {
        if (isActive) {
          setIsLoadingWorkspaces(false);
        }
      }
    };

    void fetchWorkspaces();

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [dispatch, state.selectedWorkspaceId]);

  const workspaceButtonLabel = React.useMemo(() => {
    if (isLoadingWorkspaces) {
      return t('common.loading');
    }
    if (hasWorkspaceError) {
      return t('navigation.workspaceSelector.error');
    }
    if (selectedWorkspace) {
      return selectedWorkspace.name;
    }
    if (workspaces.length === 0) {
      return t('navigation.workspaceSelector.empty');
    }
    return t('navigation.workspaceSelector.selectLabel');
  }, [hasWorkspaceError, isLoadingWorkspaces, selectedWorkspace, t, workspaces.length]);

  const handleWorkspaceSelect = (workspaceId: string) => {
    dispatch({ type: 'SET_SELECTED_WORKSPACE', payload: workspaceId });
    navigate(ROUTES.WORKSPACES);
  };

  const checkUserSettings = async (): Promise<SettingsValidationResult | null> => {
    try {
      const userId = appState.user.id;
      if (!userId) {
        logger.error('User ID not found');
        return null;
      }

      const response = await apiClient.get<UserSettingsResponse>(`/users/${userId}/settings`);
      const settings: UserSettings = response.data;

      return validateUserSettings(settings);
    } catch (error) {
      logger.error('Failed to check user settings', { error });
      return null;
    }
  };

  const handleCreateWorkspace = async () => {
    logger.debug('handleCreateWorkspace called');

    const result = await checkUserSettings();
    logger.debug('checkUserSettings result', { result });

    if (!result) {
      navigate(ROUTES.WORKSPACE_WIZARD);
      return;
    }

    setValidationResult(result);

    if (!result.isValid) {
      setShowSettingsCheckDialog(true);
    } else {
      navigate(ROUTES.WORKSPACE_WIZARD);
    }
  };

  const handleProceedFromDialog = () => {
    navigate(ROUTES.WORKSPACE_WIZARD);
  };

  const shouldShowWorkspaceSelector = React.useMemo(() => {
    const isProfilePage = location.pathname === ROUTES.PROFILE;
    const isSettingsPage = location.pathname === ROUTES.SETTINGS;
    return state.currentModule === 'workspace' && !isProfilePage && !isSettingsPage;
  }, [state.currentModule, location.pathname]);

  return (
    <header className="h-10 border-b border-border/50 bg-gradient-to-r from-card to-card/95 backdrop-blur-md px-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-bold cursor-pointer flex items-center gap-2 hover:opacity-80 transition-all duration-300 group" onClick={() => navigate(ROUTES.WORKSPACES)}>
          <img src="/logo.png" alt="Aileron" className="h-4 w-4 group-hover:scale-110 transition-transform duration-300" />
          <span className="relative bg-gradient-to-r from-primary to-gray-700 bg-clip-text text-transparent">
            {t('navigation.brand.title')}
            <div className="absolute bottom-0 left-0 w-0 h-0.5 bg-gradient-to-r from-primary to-gray-700 group-hover:w-full transition-all duration-300"></div>
          </span>
        </h1>

        {shouldShowWorkspaceSelector && (
          <div className="flex items-center gap-1.5 ml-2 pl-2 border-l border-border/50">
            <div className="flex items-center gap-1">
              <Folder className="h-3 w-3 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">{t('navigation.workspaceSelector.label')}</span>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1 px-2"
                  data-testid="workspace-selector-trigger"
                  title={selectedWorkspace?.name || undefined}
                >
                  <span className="truncate max-w-32 text-xs">
                    {workspaceButtonLabel}
                  </span>
                  <ChevronDown className="h-2.5 w-2.5 flex-shrink-0" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-72" align="start">
                <DropdownMenuLabel>{t('navigation.workspaceSelector.selectLabel')}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {isLoadingWorkspaces ? (
                  <DropdownMenuItem
                    disabled
                    data-testid="workspace-selector-loading"
                    className="py-6 text-sm text-muted-foreground"
                  >
                    {t('common.loading')}
                  </DropdownMenuItem>
                ) : hasWorkspaceError ? (
                  <DropdownMenuItem
                    disabled
                    data-testid="workspace-selector-error"
                    className="py-4 text-sm text-destructive"
                  >
                    {t('navigation.workspaceSelector.error')}
                  </DropdownMenuItem>
                ) : workspaces.length === 0 ? (
                  <DropdownMenuItem
                    disabled
                    data-testid="workspace-selector-empty"
                    className="py-6 text-sm text-muted-foreground"
                  >
                    {t('navigation.workspaceSelector.empty')}
                  </DropdownMenuItem>
                ) : (
                  <div className="max-h-64 overflow-y-auto">
                    {workspaces.map(workspace => {
                      const isActive = workspace.id === state.selectedWorkspaceId;
                      return (
                        <DropdownMenuItem
                          key={workspace.id}
                          data-testid={`workspace-option-${workspace.id}`}
                          onSelect={() => handleWorkspaceSelect(workspace.id)}
                          className={cn(
                            'flex w-full flex-col items-start gap-1 rounded-md px-3 py-2 text-left',
                            workspace.id === state.selectedWorkspaceId && 'bg-accent text-accent-foreground'
                          )}
                        >
                          <span className="flex items-center gap-2 text-sm font-medium">
                            {workspace.name}
                            {isActive && (
                              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                                {t('navigation.workspaceSelector.active')}
                              </span>
                            )}
                          </span>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge variant="outline" className="text-[10px]">
                              {getProvisionerLabel(workspace.provisioner)}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={cn('text-[10px]', getPhaseBadgeClassName(workspace.overallPhase ?? workspace.runtimeStatus))}
                            >
                              {getPhaseLabel(workspace.overallPhase ?? workspace.runtimeStatus)}
                            </Badge>
                            {workspace.targetNamespace && (
                              <Badge variant="outline" className="text-[10px]">
                                {t('navigation.workspaceSelector.namespace', {
                                  name: workspace.targetNamespace,
                                })}
                              </Badge>
                            )}
                          </div>
                          {workspace.description && (
                            <span className="w-full truncate text-xs text-muted-foreground">
                              {workspace.description}
                            </span>
                          )}
                          {workspace.owner?.displayName && (
                            <span className="text-xs text-muted-foreground">
                              {t('navigation.workspaceSelector.owner', {
                                name: workspace.owner.displayName,
                              })}
                            </span>
                          )}
                        </DropdownMenuItem>
                      );
                    })}
                  </div>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              title={t('navigation.workspaceSelector.newWorkspace')}
              onClick={handleCreateWorkspace}
            >
              <FolderPlus className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 bg-muted/50 rounded-md p-0.5">
            <Button
              variant={state.currentModule === 'workspace' ? 'default' : 'ghost'}
              size="sm"
              className={`gap-1 transition-all duration-300 h-7 px-2 text-xs ${
                state.currentModule === 'workspace'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setActiveModule('workspace')}
            >
              <Folder className="h-3 w-3" />
              {t('navigation.workspace')}
            </Button>
          </div>

          <div className="flex items-center gap-0.5 bg-muted/50 rounded-md p-0.5">
            <Button
              variant={state.currentModule === 'automation' ? 'default' : 'ghost'}
              size="sm"
              className={`gap-1 transition-all duration-300 h-7 px-2 text-xs ${
                state.currentModule === 'automation'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setActiveModule('automation')}
            >
              <Clock className="h-3 w-3" />
              {t('navigation.automation')}
            </Button>

            <Button
              variant={state.currentModule === 'marketplace' ? 'default' : 'ghost'}
              size="sm"
              className={`gap-1 transition-all duration-300 h-7 px-2 text-xs ${
                state.currentModule === 'marketplace'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setActiveModule('marketplace')}
            >
              <Store className="h-3 w-3" />
              {t('navigation.marketplace')}
            </Button>

            <Button
              variant={state.currentModule === 'knowledge-base' ? 'default' : 'ghost'}
              size="sm"
              className={`gap-1 transition-all duration-300 h-7 px-2 text-xs ${
                state.currentModule === 'knowledge-base'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setActiveModule('knowledge-base')}
            >
              <Library className="h-3 w-3" />
              {t('navigation.knowledgeBaseCenter')}
            </Button>
          </div>

          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 transition-all duration-300 hover:bg-muted text-muted-foreground hover:text-foreground"
            onClick={toggleFullscreen}
            title={isFullscreen ? t('navigation.fullscreen.exit') : t('navigation.fullscreen.enter')}
          >
            {isFullscreen ? <Minimize className="h-3 w-3" /> : <Maximize className="h-3 w-3" />}
          </Button>
        </div>

        <div className="flex items-center gap-2">
          {isAuthenticated && user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-8 w-8 rounded-full hover:bg-primary/10 transition-all duration-300 group p-0" title={userDisplayName}>
                  <Avatar className="h-6 w-6 ring-1 ring-transparent group-hover:ring-primary/30 transition-all duration-300">
                    <AvatarFallback className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground group-hover:from-primary/90 group-hover:to-primary/70 transition-all duration-300 text-xs">
                      {userInitials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/20 to-primary/10 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10"></div>
                </Button>
              </DropdownMenuTrigger>

              <DropdownMenuContent className="w-60 bg-card/95 backdrop-blur-md border border-border/50 shadow-xl" align="end" forceMount>
                <DropdownMenuLabel className="font-normal p-3">
                  <div className="flex items-center space-x-2">
                    <Avatar className="h-9 w-9 ring-2 ring-primary/20">
                      <AvatarFallback className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground text-sm">
                        {userInitials}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col space-y-0.5">
                      <p className="text-xs font-semibold leading-none text-foreground">{userDisplayName}</p>
                      {userEmail && (
                        <p className="text-[11px] leading-none text-muted-foreground">
                          {userEmail}
                        </p>
                      )}
                    </div>
                  </div>
                </DropdownMenuLabel>

                <DropdownMenuSeparator className="bg-border/50" />

                <DropdownMenuGroup className="p-1.5">
                  <DropdownMenuItem
                    className="cursor-pointer rounded-md hover:bg-primary/10 transition-colors duration-200 p-2"
                    onClick={() => navigate(ROUTES.PROFILE)}
                  >
                    <User className="mr-2 h-3.5 w-3.5 text-primary" />
                    <span className="text-xs font-medium">{t('navigation.userMenu.profile')}</span>
                  </DropdownMenuItem>

                  <DropdownMenuItem
                    className="cursor-pointer rounded-md hover:bg-primary/10 transition-colors duration-200 p-2"
                    onClick={() => navigate(ROUTES.SETTINGS)}
                  >
                    <Settings className="mr-2 h-3.5 w-3.5 text-primary" />
                    <span className="text-xs font-medium">{t('navigation.userMenu.settings')}</span>
                  </DropdownMenuItem>
                </DropdownMenuGroup>

                <DropdownMenuSeparator className="bg-border/50" />

                <div className="p-1.5">
                  <DropdownMenuItem
                    className="cursor-pointer text-destructive focus:text-destructive hover:bg-destructive/10 rounded-md transition-colors duration-200 p-2"
                    onClick={async () => {
                      try {
                        await logout();
                        navigate('/login');
                      } catch (error) {
                        logger.error('Logout failed', { error });
                      }
                    }}
                  >
                    <LogOut className="mr-2 h-3.5 w-3.5" />
                    <span className="text-xs font-medium">{t('navigation.userMenu.logout')}</span>
                  </DropdownMenuItem>
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-3 text-xs font-medium hover:bg-primary/10 transition-all duration-300"
              onClick={() => navigate('/login')}
            >
              <LogIn className="h-3 w-3 mr-1.5" />
              {t('navigation.userMenu.login')}
            </Button>
          )}
        </div>
      </div>

      <SettingsCheckDialog
        open={showSettingsCheckDialog}
        onOpenChange={setShowSettingsCheckDialog}
        validationResult={validationResult}
        onProceed={handleProceedFromDialog}
      />
    </header>
  );
};

export default GlobalNavigation;
