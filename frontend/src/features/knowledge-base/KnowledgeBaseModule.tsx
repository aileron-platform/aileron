import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { KnowledgeBaseShell } from './components/KnowledgeBaseShell';
import { KnowledgeBaseProvider } from './providers/KnowledgeBaseProvider';
import { KnowledgeBaseCreateRoute } from './routes/KnowledgeBaseCreateRoute';
import { KnowledgeBaseDetailRoute } from './routes/KnowledgeBaseDetailRoute';
import { KnowledgeBaseListRoute } from './routes/KnowledgeBaseListRoute';

export const KnowledgeBaseModule: React.FC = () => {
  return (
    <KnowledgeBaseProvider>
      <KnowledgeBaseShell>
        <Routes>
          <Route index element={<KnowledgeBaseListRoute />} />
          <Route path="new" element={<KnowledgeBaseCreateRoute />} />
          <Route path=":knowledgeBaseId/*" element={<KnowledgeBaseDetailRoute />} />
          <Route path="*" element={<Navigate to="." replace />} />
        </Routes>
      </KnowledgeBaseShell>
    </KnowledgeBaseProvider>
  );
};

export default KnowledgeBaseModule;
