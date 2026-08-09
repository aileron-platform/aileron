export { PLATFORM_ROLES } from '@/features/auth/public';

interface UserDisplayFields {
  firstName: string | null;
  lastName: string | null;
  username: string;
}

export const getAdminUserDisplayName = (user: UserDisplayFields): string =>
  [user.firstName, user.lastName].filter(Boolean).join(' ') || user.username;
