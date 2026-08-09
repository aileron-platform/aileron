/**
 * 
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
