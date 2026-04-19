import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';

import { QueuedMessagesPanel } from './QueuedMessagesPanel';

const t = (key: string) => key;

describe('QueuedMessagesPanel', () => {
  it('disables delete for dispatching messages', () => {
    const onDelete = vi.fn();
    render(
      <QueuedMessagesPanel
        messages={[
          {
            message_id: 'msg-1',
            content_preview: 'processing prompt',
            queue_position: 1,
            status: 'dispatching',
          },
        ]}
        onDelete={onDelete}
        onCopy={vi.fn()}
        t={t}
      />,
    );

    const deleteButton = screen.getByTitle('Processing');
    expect(deleteButton).toBeDisabled();
    fireEvent.click(deleteButton);
    expect(onDelete).not.toHaveBeenCalled();
  });
});
