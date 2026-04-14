/**
 * main.tsx - 應用程式入口點
 * 
 * React 應用程式的主要入口檔案
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import AppPage from './pages/AppPage';
import './shared/design-system/styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppPage />
  </React.StrictMode>,
);
