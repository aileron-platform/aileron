import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { UserManagementPage } from './UserManagementPage';

interface UserManagementModuleProps {
  navigationSlot: React.ReactNode;
}

export const UserManagementModule: React.FC<UserManagementModuleProps> = ({ navigationSlot }) => (
  <Routes>
    <Route path="/" element={<Navigate to="users" replace />} />
    <Route path="users" element={<UserManagementPage navigationSlot={navigationSlot} />} />
    <Route path="role-issues" element={<UserManagementPage navigationSlot={navigationSlot} />} />
    <Route path="disabled" element={<UserManagementPage navigationSlot={navigationSlot} />} />
    <Route path="groups" element={<UserManagementPage navigationSlot={navigationSlot} />} />
    <Route path="groups/empty" element={<UserManagementPage navigationSlot={navigationSlot} />} />
    <Route path="groups/:groupId/members" element={<UserManagementPage navigationSlot={navigationSlot} />} />
  </Routes>
);
