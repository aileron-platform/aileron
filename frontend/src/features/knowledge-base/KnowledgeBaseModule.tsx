import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { KnowledgeBaseProvider } from './providers/KnowledgeBaseProvider';
import { KnowledgeBaseCreateRoute } from './routes/KnowledgeBaseCreateRoute';
import { KnowledgeBaseDetailRoute } from './routes/KnowledgeBaseDetailRoute';
import { KnowledgeBaseListRoute } from './routes/KnowledgeBaseListRoute';
import { KnowledgeBaseShellAdapter } from './components/KnowledgeBaseShellAdapter';

interface KnowledgeBaseModuleProps {
  navigationSlot: React.ReactNode;
}

export const KnowledgeBaseModule: React.FC<KnowledgeBaseModuleProps> = ({ navigationSlot }) => {
  return (
    <KnowledgeBaseProvider>
      <Routes>
        <Route index element={<KnowledgeBaseListRoute navigationSlot={navigationSlot} />} />
        <Route
          path="new"
          element={<KnowledgeBaseCreateRoute navigationSlot={navigationSlot} />}
        />
        <Route
          path=":knowledgeBaseId/*"
          element={<KnowledgeBaseDetailRoute navigationSlot={navigationSlot} />}
        />
        <Route
          path="*"
          element={(
            <KnowledgeBaseShellAdapter
              navigationSlot={navigationSlot}
              surface={{ kind: 'state', content: <Navigate to="." replace /> }}
            />
          )}
        />
      </Routes>
    </KnowledgeBaseProvider>
  );
};
