import {
  FileDiff,
  Folder,
  GitBranch,
  History,
  Link2,
  Settings,
  Share2,
  type LucideIcon,
} from 'lucide-react';
import type {
  KnowledgeBaseFeatureId,
  KnowledgeBaseVersionControlSubView,
} from '../model/knowledgeBaseShellModel';

interface KnowledgeBaseNavigationSubItem {
  id: KnowledgeBaseVersionControlSubView;
  labelKey: string;
  icon: LucideIcon;
}

interface KnowledgeBaseNavigationItem {
  id: KnowledgeBaseFeatureId;
  icon: LucideIcon;
  labelKey: string;
  subItems?: KnowledgeBaseNavigationSubItem[];
  countId?: 'shares' | 'attachments';
}

export const KNOWLEDGE_BASE_NAVIGATION_ITEMS: KnowledgeBaseNavigationItem[] = [
  { id: 'files', icon: Folder, labelKey: 'knowledgeBase.navigation.files' },
  {
    id: 'version-control',
    icon: GitBranch,
    labelKey: 'knowledgeBase.navigation.versionControl',
    subItems: [
      { id: 'changes', labelKey: 'shared.versionControl.mode.fileChanges', icon: FileDiff },
      { id: 'history', labelKey: 'shared.versionControl.mode.commitHistory', icon: History },
    ],
  },
  {
    id: 'sharing',
    icon: Share2,
    labelKey: 'knowledgeBase.navigation.sharing',
    countId: 'shares',
  },
  {
    id: 'workspaces',
    icon: Link2,
    labelKey: 'knowledgeBase.navigation.workspaces',
    countId: 'attachments',
  },
  { id: 'settings', icon: Settings, labelKey: 'knowledgeBase.navigation.settings' },
];
