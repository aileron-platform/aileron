import type { LucideIcon } from 'lucide-react';
import { Bot, Brain, Command, Sparkles, Zap } from 'lucide-react';
import type { DocumentWorkbenchConfig } from './model/documentResourceTypes';

const DOCUMENT_WORKBENCH_ICONS = {
  command: Command,
  memory: Brain,
  outputStyle: Sparkles,
  rules: Zap,
  subagents: Bot,
} as const satisfies Record<string, LucideIcon>;

export const getDocumentWorkbenchIcon = (
  metaKey: DocumentWorkbenchConfig['metaKey'],
): LucideIcon => {
  switch (metaKey) {
    case 'slash-commands':
      return DOCUMENT_WORKBENCH_ICONS.command;
    case 'output-styles':
      return DOCUMENT_WORKBENCH_ICONS.outputStyle;
    case 'subagents':
      return DOCUMENT_WORKBENCH_ICONS.subagents;
    case 'prompts':
      return DOCUMENT_WORKBENCH_ICONS.command;
    case 'rules':
      return DOCUMENT_WORKBENCH_ICONS.rules;
    case 'memory':
      return DOCUMENT_WORKBENCH_ICONS.memory;
    default:
      return DOCUMENT_WORKBENCH_ICONS.command;
  }
};
