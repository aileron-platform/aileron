import { describe, expect, it } from 'vitest';
import {
  getOpenSpecDocumentKind,
  parseOpenSpecSpecOutline,
  parseOpenSpecTasks,
  toggleOpenSpecTask,
} from './openSpecMarkdown';

describe('openSpecMarkdown', () => {
  it('detects OpenSpec tasks and spec documents by path', () => {
    expect(getOpenSpecDocumentKind('/openspec/changes/demo/tasks.md')).toBe('tasks');
    expect(getOpenSpecDocumentKind('/openspec/changes/demo/specs/a/spec.md')).toBe('spec');
    expect(getOpenSpecDocumentKind('/docs/guide.md')).toBeNull();
  });

  it('parses tasks sections and toggles checklist items', () => {
    const content = `## 1. Navigation\n\n- [x] 1.1 Add menu\n- [ ] 1.2 Add route`;
    const sections = parseOpenSpecTasks(content);

    expect(sections).toHaveLength(1);
    expect(sections[0].tasks).toHaveLength(2);
    expect(sections[0].tasks[1].checked).toBe(false);

    const nextContent = toggleOpenSpecTask(content, sections[0].tasks[1].lineIndex, true);
    expect(nextContent).toContain('- [x] 1.2 Add route');
  });

  it('parses requirement and scenario outline from spec markdown', () => {
    const content = `## ADDED Requirements

### Requirement: OpenSpec navigation shall group changes
#### Scenario: User sees proposal
#### Scenario: User sees tasks
`;

    const outline = parseOpenSpecSpecOutline(content);
    expect(outline).toHaveLength(1);
    expect(outline[0].title).toBe('OpenSpec navigation shall group changes');
    expect(outline[0].scenarios.map((scenario) => scenario.title)).toEqual([
      'User sees proposal',
      'User sees tasks',
    ]);
  });
});
