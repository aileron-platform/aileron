export { RequireAuth, PublicRoute } from './components/RequireAuth';
export { RequirePlatformAdmin } from './components/RequirePlatformAdmin';
export { RequirePlatformMember } from './components/RequirePlatformMember';
export { RequirePlatformOperation } from './components/RequirePlatformOperation';
export { AuthorizationDeniedState } from './components/AuthorizationDeniedState';
export { AuthProvider } from './contexts/AuthContext';
export { useAuth } from './hooks/useAuth';
export type { PlatformRole } from './model/platformRoles';
export { PLATFORM_ROLES } from './model/platformRoles';
export type { ManagerSessionUser } from './services/ManagerSessionService';
export { executionGrantBroker } from './services/ExecutionGrantBroker';

export const loadLoginPage = () => import('./pages/LoginPage');
export const loadRegisterPage = () => import('./pages/RegisterPage');
