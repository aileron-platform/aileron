/**
 * AppPage - 主要應用程式頁面
 * 
 * 應用程式的主要入口頁面
 */

import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AppShell } from '../app/AppShell';

export const AppPage: React.FC = () => {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true
      }}
    >
      <AppShell />
    </BrowserRouter>
  );
};

export default AppPage;
