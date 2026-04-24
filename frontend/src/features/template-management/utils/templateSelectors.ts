import type { Template, TemplateFeatureFlags, TemplateFeatureKey, CliType } from '@/shared/types/templates';

export const buildFeatureFlags = (template: Template): TemplateFeatureFlags => ({
  hasMcp: template.mcpServers.length > 0,
  hasCommands: template.commands.length > 0,
  hasHooks: template.hooks.length > 0,
  hasAgentsMd: Boolean(template.agentsMd && template.agentsMd.trim().length > 0),
  hasAgents: template.agents.length > 0,
  hasOutputStyle: template.outputStyle.length > 0,
  hasScripts: template.scripts.length > 0,
  hasSkills: template.skills.length > 0,
});

export const templateSupportsFeature = (
  template: Template,
  feature: TemplateFeatureKey,
): boolean => {
  const flags = buildFeatureFlags(template);
  switch (feature) {
    case 'mcp':
      return flags.hasMcp;
    case 'commands':
      return flags.hasCommands;
    case 'hooks':
      return flags.hasHooks;
    case 'agentsMd':
      return flags.hasAgentsMd;
    case 'agents':
      return flags.hasAgents;
    case 'outputStyle':
      return flags.hasOutputStyle;
    case 'scripts':
      return flags.hasScripts;
    case 'skills':
      return flags.hasSkills;
    default:
      return false;
  }
};

export const createTemplateSearchIndex = (template: Template): string => {
  const { name, description, author, keywords, categoryName, version } = template;
  return [
    name,
    description,
    author.name,
    author.email,
    author.url,
    categoryName,
    version,
    ...(keywords ?? []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
};

export const filterTemplates = (
  templates: Template[],
  {
    searchTerm,
    categoryId,
    feature,
    cliType,
  }: {
    searchTerm?: string;
    categoryId?: string;
    feature?: TemplateFeatureKey | 'all' | TemplateFeatureKey[];
    cliType?: CliType | 'all';
  },
): Template[] => {
  const normalizedSearch = searchTerm?.trim().toLowerCase();
  return templates.filter(template => {
    if (categoryId && categoryId !== 'all' && template.categoryId !== categoryId) {
      return false;
    }

    if (cliType && cliType !== 'all') {
      const effectiveCli = template.cliType ?? 'claude-code';
      if (effectiveCli !== cliType) return false;
    }

    // 支持單個特性或多個特性的篩選（多選時使用 OR 邏輯）
    if (feature) {
      const features = Array.isArray(feature) ? feature : [feature];
      if (features.length > 0 && !features.includes('all')) {
        const hasAnyFeature = features.some(f => templateSupportsFeature(template, f));
        if (!hasAnyFeature) return false;
      }
    }

    if (normalizedSearch && normalizedSearch.length > 0) {
      const haystack = createTemplateSearchIndex(template);
      if (!haystack.includes(normalizedSearch)) {
        return false;
      }
    }

    return true;
  });
};
