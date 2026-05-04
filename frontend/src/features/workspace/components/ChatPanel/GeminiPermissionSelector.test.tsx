import { fireEvent, render, screen } from '@/__tests__/utils/render';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { GeminiPermissionSelector } from './GeminiPermissionSelector';
import enChat from '@/shared/locales/en/modules/workspace/chat';
import zhTWChat from '@/shared/locales/zh-TW/modules/workspace/chat';

const t = (key: string) => key;

vi.mock('@/shared/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  DropdownMenuContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({
    children,
    onClick,
    className,
  }: {
    children: ReactNode;
    onClick?: () => void;
    className?: string;
  }) => (
    <button type="button" onClick={onClick} className={className}>
      {children}
    </button>
  ),
}));

describe('GeminiPermissionSelector', () => {
  it('lists four Gemini modes and reports changes', () => {
    const onChange = vi.fn();
    render(
      <GeminiPermissionSelector
        value="default"
        onChange={onChange}
        t={t}
      />,
    );
    expect(screen.getAllByText('workspace.chat.input.geminiPermission.default.label')).toHaveLength(2);
    expect(screen.getByText('workspace.chat.input.geminiPermission.label')).toBeInTheDocument();
    expect(screen.getByText('workspace.chat.input.geminiPermission.description')).toBeInTheDocument();
    expect(screen.getByText('workspace.chat.input.geminiPermission.yolo.label')).toBeInTheDocument();
    expect(screen.getByText('workspace.chat.input.geminiPermission.autoEdit.label')).toBeInTheDocument();
    expect(screen.getByText('workspace.chat.input.geminiPermission.plan.label')).toBeInTheDocument();

    fireEvent.click(screen.getByText('workspace.chat.input.geminiPermission.yolo.label'));
    expect(onChange).toHaveBeenCalledWith('yolo');
  });

  it('applies warning classes for yolo mode', () => {
    render(
      <GeminiPermissionSelector
        value="yolo"
        onChange={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTitle('workspace.chat.input.geminiPermission.label').className).toContain('border-amber-500/60');
  });

  it('shows apply-on-next hint only when requested', () => {
    const { rerender } = render(
      <GeminiPermissionSelector
        value="default"
        onChange={vi.fn()}
        appliesOnNextHint
        t={t}
      />,
    );

    expect(screen.getByText('workspace.chat.input.geminiPermission.applyOnNextHint')).toBeInTheDocument();

    rerender(
      <GeminiPermissionSelector
        value="default"
        onChange={vi.fn()}
        appliesOnNextHint={false}
        t={t}
      />,
    );

    expect(screen.queryByText('workspace.chat.input.geminiPermission.applyOnNextHint')).not.toBeInTheDocument();
  });

  it('keeps YOLO warning copy in both locales', () => {
    expect(enChat.input.geminiPermission.yoloWarning).toContain('shell commands');
    expect(enChat.input.geminiPermission.yoloWarning).toContain('network requests');
    expect(zhTWChat.input.geminiPermission.yoloWarning).toContain('shell 指令');
    expect(zhTWChat.input.geminiPermission.yoloWarning).toContain('網路請求');
  });
});
