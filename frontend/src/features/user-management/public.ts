export const loadUserManagementModule = () =>
  import('./UserManagementModule').then(({ UserManagementModule }) => ({
    default: UserManagementModule,
  }));
