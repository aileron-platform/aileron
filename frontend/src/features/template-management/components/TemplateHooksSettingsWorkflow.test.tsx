import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TemplateHooksSettingsWorkflow from './TemplateHooksSettingsWorkflow';
import type { HookFormValue } from '@/features/template-management/features/template-editor/formTypes';

const toastMock = vi.fn();
const saveHooksConfigMock = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'template.editor.tabs.hooks': 'Hooks',
        'template.detail.hooks.header.title': 'Template Hooks',
        'template.detail.hooks.badge': 'badge',
        'template.editor.hooks.actions.add': 'Add Hook',
        'template.editor.hooks.empty.title': 'No hooks yet',
        'template.editor.hooks.empty.description': 'Create hook',
        'template.detail.hooks.empty.title': 'No hooks',
        'template.detail.hooks.empty.description': 'Nothing here',
        'template.detail.hooks.actions.download': 'Download Hooks',
        'template.detail.hooks.downloadFileName': 'hooks.json',
        'template.detail.hooks.toasts.downloadSuccess.title': 'Downloaded',
        'template.detail.hooks.toasts.downloadSuccess.description': 'Hooks downloaded',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/features/template-management/features/template-editor/hooks/useTemplateApi', () => ({
  useTemplateApi: () => ({
    saveHooksConfig: saveHooksConfigMock,
  }),
}));

vi.mock('@/features/template-management/components/HookCard', () => ({
  default: ({
    hook,
    showActions,
    onDelete,
  }: {
    hook: HookFormValue;
    showActions?: boolean;
    onDelete?: (hookId: string) => void;
  }) => (
    <div data-testid={`hook-card-${hook.localId}`}>
      <span>{hook.event}</span>
      {showActions ? (
        <button type="button" onClick={() => onDelete?.(hook.localId)}>
          delete-{hook.localId}
        </button>
      ) : null}
    </div>
  ),
}));

vi.mock('./TemplateHookDialog', () => ({
  TemplateHookDialog: ({
    open,
    onSave,
  }: {
    open: boolean;
    onSave: (hook: HookFormValue) => void;
  }) =>
    open ? (
      <div data-testid="hook-dialog">
        <button
          type="button"
          onClick={() =>
            onSave({
              localId: 'hook-2',
              event: 'Stop',
              matchers: [{ matcher: '*', hooks: [{ type: 'command', command: 'echo stop', timeout: 10 }] }],
            })
          }
        >
          save-hook
        </button>
      </div>
    ) : null,
}));

describe('TemplateHooksSettingsWorkflow', () => {
  const hooks: HookFormValue[] = [
    {
      localId: 'hook-1',
      event: 'PreToolUse',
      matchers: [{ matcher: '*', hooks: [{ type: 'command', command: 'echo test', timeout: 5 }] }],
    },
  ];

  beforeEach(() => {
    toastMock.mockReset();
    saveHooksConfigMock.mockReset().mockResolvedValue(true);
  });

  it('editable 模式新增 hook 會更新本地狀態並儲存', async () => {
    const onHooksChange = vi.fn();

    render(
      <TemplateHooksSettingsWorkflow
        templateId="tpl-1"
        hooks={hooks}
        editable
        onHooksChange={onHooksChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Add Hook' }));
    fireEvent.click(screen.getByRole('button', { name: 'save-hook' }));

    await waitFor(() => {
      expect(onHooksChange).toHaveBeenCalledWith([
        hooks[0],
        expect.objectContaining({ localId: 'hook-2', event: 'Stop' }),
      ]);
      expect(saveHooksConfigMock).toHaveBeenCalledWith([
        hooks[0],
        expect.objectContaining({ localId: 'hook-2', event: 'Stop' }),
      ]);
    });
  });

  it('editable 模式刪除 hook 會更新本地狀態並儲存', async () => {
    const onHooksChange = vi.fn();

    render(
      <TemplateHooksSettingsWorkflow
        templateId="tpl-1"
        hooks={hooks}
        editable
        onHooksChange={onHooksChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'delete-hook-1' }));

    await waitFor(() => {
      expect(onHooksChange).toHaveBeenCalledWith([]);
      expect(saveHooksConfigMock).toHaveBeenCalledWith([]);
    });
  });

  it('editable 模式只顯示單一 hooks header 並保留數量 badge 與新增按鈕', () => {
    render(
      <TemplateHooksSettingsWorkflow
        templateId="tpl-1"
        hooks={hooks}
        editable
      />
    );

    expect(screen.getByRole('button', { name: 'Add Hook' })).toBeInTheDocument();
    expect(screen.getByText('badge')).toBeInTheDocument();
    expect(screen.getAllByText('Hooks')).toHaveLength(1);
  });
});
