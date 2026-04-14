export interface ParsedTaskItem {
  id: string;
  lineIndex: number;
  checked: boolean;
  label: string;
}

export interface ParsedTaskSection {
  id: string;
  title: string;
  tasks: ParsedTaskItem[];
}

export interface ParsedSpecScenario {
  id: string;
  title: string;
}

export interface ParsedSpecRequirement {
  id: string;
  title: string;
  scenarios: ParsedSpecScenario[];
}

const slugify = (value: string): string =>
  value
    .toLowerCase()
    .trim()
    .replace(/[`*_~]/g, '')
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '');

export const getOpenSpecDocumentKind = (
  filePath?: string,
): 'tasks' | 'spec' | null => {
  if (!filePath?.startsWith('/openspec/')) {
    return null;
  }
  if (filePath.endsWith('/tasks.md')) {
    return 'tasks';
  }
  if (filePath.endsWith('/spec.md')) {
    return 'spec';
  }
  return null;
};

export const parseOpenSpecTasks = (content: string): ParsedTaskSection[] => {
  const lines = content.split('\n');
  const sections: ParsedTaskSection[] = [];
  let currentSection: ParsedTaskSection | null = null;

  lines.forEach((line, lineIndex) => {
    const sectionMatch = line.match(/^##\s+(.+)$/);
    if (sectionMatch) {
      currentSection = {
        id: `${slugify(sectionMatch[1]) || 'section'}-${lineIndex}`,
        title: sectionMatch[1].trim(),
        tasks: [],
      };
      sections.push(currentSection);
      return;
    }

    const taskMatch = line.match(/^- \[( |x|X)\]\s+(.+)$/);
    if (!taskMatch) {
      return;
    }

    if (!currentSection) {
      currentSection = {
        id: 'default-section',
        title: 'Tasks',
        tasks: [],
      };
      sections.push(currentSection);
    }

    currentSection.tasks.push({
      id: `${currentSection.id}-task-${currentSection.tasks.length}`,
      lineIndex,
      checked: taskMatch[1].toLowerCase() === 'x',
      label: taskMatch[2].trim(),
    });
  });

  return sections.filter((section) => section.tasks.length > 0);
};

export const toggleOpenSpecTask = (
  content: string,
  lineIndex: number,
  checked: boolean,
): string => {
  const lines = content.split('\n');
  const currentLine = lines[lineIndex];
  if (!currentLine) {
    return content;
  }

  lines[lineIndex] = currentLine.replace(/^- \[( |x|X)\]/, checked ? '- [x]' : '- [ ]');
  return lines.join('\n');
};

export const parseOpenSpecSpecOutline = (content: string): ParsedSpecRequirement[] => {
  const lines = content.split('\n');
  const requirements: ParsedSpecRequirement[] = [];
  let currentRequirement: ParsedSpecRequirement | null = null;

  lines.forEach((line, lineIndex) => {
    const requirementMatch = line.match(/^###\s+Requirement:\s+(.+)$/);
    if (requirementMatch) {
      currentRequirement = {
        id: `${slugify(`requirement-${requirementMatch[1]}`) || 'requirement'}-${lineIndex}`,
        title: requirementMatch[1].trim(),
        scenarios: [],
      };
      requirements.push(currentRequirement);
      return;
    }

    const scenarioMatch = line.match(/^####\s+Scenario:\s+(.+)$/);
    if (scenarioMatch && currentRequirement) {
      currentRequirement.scenarios.push({
        id: `${slugify(`scenario-${scenarioMatch[1]}`) || 'scenario'}-${lineIndex}`,
        title: scenarioMatch[1].trim(),
      });
    }
  });

  return requirements;
};

