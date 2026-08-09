import { useEffect, useMemo, useRef, useState } from 'react';
import type { CreateDraftPayload } from '../api/threadApi';
import { getPreferredThreadSettings, setPreferredThreadSettings } from '../storage/aiChatStorage';
import type { OutgoingMessage, Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { normalizeThreadSettings, type ThreadSettings } from '../model/threadSettingsModel';
import { ChatInputArea } from './ChatInputArea';

export interface NewTaskSubmitPayload {
  settings: CreateDraftPayload;
  message: OutgoingMessage;
}

interface NewTaskPromptBoxProps {
  capabilities: WorkspaceCapabilities;
  draftThread?: Thread | null;
  onEnsureDraft: (settings: CreateDraftPayload) => Promise<Thread>;
  onSubmit: (payload: NewTaskSubmitPayload) => void;
  onPatchDraft: (patch: Partial<ThreadSettings> & { draftMessage?: OutgoingMessage | null }) => void;
}

const buildDefaultSettings = (capabilities: WorkspaceCapabilities): CreateDraftPayload => {
  const preferred = getPreferredThreadSettings(capabilities);
  if (preferred) return preferred;
  const tool = capabilities.tools.find((item) => item.id === capabilities.defaultTool) ?? capabilities.tools[0];
  return {
    agenticTool: tool.id,
    model: tool.defaultModel,
    claudeMode: tool.defaultMode,
  };
};

export const NewTaskPromptBox = ({
  capabilities,
  draftThread,
  onEnsureDraft,
  onSubmit,
  onPatchDraft,
}: NewTaskPromptBoxProps) => {
  const [settings, setSettings] = useState<CreateDraftPayload>(() => buildDefaultSettings(capabilities));
  const [ensuredDraft, setEnsuredDraft] = useState<Thread | null>(null);
  const ensuredDraftRef = useRef<Thread | null>(draftThread ?? null);
  const activeDraft = draftThread ?? ensuredDraft;

  useEffect(() => {
    if (draftThread) {
      ensuredDraftRef.current = draftThread;
      setEnsuredDraft(draftThread);
    }
  }, [draftThread]);

  useEffect(() => {
    setSettings((current) => normalizeThreadSettings(capabilities, current));
  }, [capabilities]);

  const inputThread = useMemo<Thread>(() => {
    if (activeDraft) return activeDraft;
    const now = new Date(0).toISOString();
    return {
      id: 'new-task-draft',
      workspaceId: 'new-task-workspace',
      userId: 'new-task-user',
      title: 'aiChat.thread.untitled',
      agenticTool: settings.agenticTool,
      model: settings.model,
      claudeMode: settings.claudeMode,
      status: 'draft',
      archived: false,
      errorCode: null,
      errorInfo: null,
      errorMessage: null,
      contextTokens: null,
      contextWindow: null,
      createdAt: now,
      updatedAt: now,
      messages: [],
      queuedMessages: [],
      draftMessage: null,
    };
  }, [activeDraft, settings]);

  const ensureDraft = async (): Promise<Thread> => {
    if (ensuredDraftRef.current) return ensuredDraftRef.current;
    const draft = await onEnsureDraft(settings);
    ensuredDraftRef.current = draft;
    setEnsuredDraft(draft);
    return draft;
  };

  const handleSubmit = (message: OutgoingMessage) => {
    const trimmedText = message.text.trim();
    if (!trimmedText && message.attachments.length === 0) return;
    onSubmit({
      settings,
      message: {
        text: trimmedText,
        attachments: message.attachments,
      },
    });
  };

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col bg-background">
      <div className="min-h-0 flex-1" />
      <ChatInputArea
        thread={inputThread}
        capabilities={capabilities}
        onSubmitDraft={handleSubmit}
        onPostMessage={() => undefined}
        onPatchDraft={(patch: Partial<ThreadSettings> & { draftMessage?: OutgoingMessage | null }) => {
          setSettings((current) => {
            const next = {
              agenticTool: patch.agenticTool ?? current.agenticTool,
              model: patch.model ?? current.model,
              claudeMode: patch.claudeMode === undefined ? current.claudeMode : patch.claudeMode,
            };
            if (patch.agenticTool || patch.model || patch.claudeMode !== undefined) {
              setPreferredThreadSettings(next);
            }
            return next;
          });
          if (ensuredDraftRef.current) {
            onPatchDraft(patch);
          }
        }}
        onEnsureThread={ensureDraft}
      />
    </section>
  );
};
