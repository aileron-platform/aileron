/**
 *
 */

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { GitBranch, History } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { FileChangesPanel } from './components/FileChangesPanel';
import { CommitHistoryPanel } from './components/CommitHistoryPanel';
import { DiffViewer } from './components/DiffViewer';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import type {
  VersionControlFileChange,
  VersionControlCommitSummary,
} from '@/shared/version-control';
import { EmptyState } from '@/shared/components/ui/empty-state';

interface VersionControlState {
  selectedFile: VersionControlFileChange | null;
  selectedCommit: VersionControlCommitSummary | null;
}

interface VersionControlActions {
  selectFile: (file: VersionControlFileChange | null) => void;
  selectCommit: (commit: VersionControlCommitSummary | null) => void;
}

const VersionControlContext =
  createContext<(VersionControlState & VersionControlActions) | null>(null);

export interface VersionControlSidebarProps {
  collapsed?: boolean;
}

export const VersionControlSidebar: React.FC<VersionControlSidebarProps> = ({ collapsed = false }) => {
  const { workspace } = useWorkspace();
  const context = useContext(VersionControlContext);
  const { t } = useI18n();

  const sidebarContent = !context ? (
    collapsed ? <CollapsedSidebarPlaceholder icon={GitBranch} /> : (
      <div className="p-4">
        <div className="text-sm text-foreground opacity-60">
          {t('workspace.versionControl.sidebar.loadingDescription')}
        </div>
      </div>
    )
  ) : collapsed ? (
    <CollapsedSidebarPlaceholder icon={GitBranch} />
  ) : workspace.versionControl?.subView === 'changes' ? (
    <FileChangesPanel onFileSelect={context.selectFile} />
  ) : (
    <CommitHistoryPanel
      selectedCommitId={context.selectedCommit ? context.selectedCommit.id : ''}
      onCommitSelect={context.selectCommit}
      onFileSelect={context.selectFile}
    />
  );

  return sidebarContent;
};

export const VersionControlMainContent: React.FC = () => {
  const { workspace } = useWorkspace();
  const context = useContext(VersionControlContext);
  const { t } = useI18n();

  if (!context) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-medium text-foreground">
              {t('workspace.versionControl.main.loadingTitle')}
            </h2>
          </div>
        </div>
        {/* Content */}
        <div className="flex-1">
          <EmptyState
            icon={GitBranch}
            title={t('workspace.versionControl.main.loadingDescription')}
          />
        </div>
      </div>
    );
  }

  const { selectedFile, selectedCommit } = context;

  if (workspace.versionControl?.subView === 'changes') {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-medium text-foreground">
              {selectedFile
                ? t('workspace.versionControl.main.changes.titleWithFile', { path: selectedFile.path })
                : t('workspace.versionControl.main.changes.titleWithoutFile')}
            </h2>
          </div>
        </div>
        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <DiffViewer
            selectedFile={selectedFile}
          />
        </div>
      </div>
    );
  } else {
    if (selectedFile) {
      return (
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium text-foreground">
                {t('workspace.versionControl.main.history.titleWithFile', { path: selectedFile.path })}
              </h2>
            </div>
          </div>
          {/* Content */}
          <div className="flex-1 overflow-hidden">
            <DiffViewer
              selectedFile={selectedFile}
            />
          </div>
        </div>
      );
    } else {
      return (
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="h-10 px-3 border-b border-border bg-card flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium text-foreground">
                {selectedCommit
                  ? t('workspace.versionControl.main.history.titleWithCommit')
                  : t('workspace.versionControl.main.history.titleWithoutCommit')}
              </h2>
            </div>
          </div>
          {/* Content */}
          <div className="flex-1">
            <EmptyState
              icon={History}
              title={selectedCommit
                ? t('workspace.versionControl.main.history.titleWithCommit')
                : t('workspace.versionControl.main.history.titleWithoutCommit')}
              description={selectedCommit
                ? t('workspace.versionControl.main.history.descriptionWithCommit')
                : t('workspace.versionControl.main.history.descriptionWithoutCommit')}
            />
          </div>
        </div>
      );
    }
  }
};

export const VersionControlProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedFile, setSelectedFile] = useState<VersionControlFileChange | null>(null);
  const [selectedCommit, setSelectedCommit] = useState<VersionControlCommitSummary | null>(null);

  const selectFile = useCallback((file: VersionControlFileChange | null) => {
    setSelectedFile(file);
  }, []);

  const selectCommit = useCallback((commit: VersionControlCommitSummary | null) => {
    setSelectedCommit(commit);
    setSelectedFile(null);
  }, []);

  const contextValue = useMemo(
    () => ({
      selectedFile,
      selectedCommit,
      selectFile,
      selectCommit,
    }),
    [selectedFile, selectedCommit, selectFile, selectCommit],
  );

  return (
    <VersionControlContext.Provider value={contextValue}>
      {children}
    </VersionControlContext.Provider>
  );
};

export const VersionControlPage: React.FC = () => {
  return (
    <VersionControlProvider>
      <VersionControlMainContent />
    </VersionControlProvider>
  );
};

export default VersionControlPage;
