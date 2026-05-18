import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: '快速開始',
      collapsed: false,
      items: [
        'quick-start/installation',
        'quick-start/services',
      ],
    },
    {
      type: 'category',
      label: '部署',
      collapsed: false,
      items: [
        'deployment/docker',
        'deployment/kubernetes',
        'deployment/environment-variables',
        'deployment/keycloak',
        'deployment/production',
        'deployment/troubleshooting',
      ],
    },
    {
      type: 'category',
      label: '架構',
      items: [
        'architecture/overview',
        'architecture/canvas-protocol',
        'architecture/workspace-manager',
        'architecture/workspace-runtime',
      ],
    },
    {
      type: 'category',
      label: '功能',
      items: [
        'features/workspace-lifecycle',
        'features/openspec',
        'features/claude-integration',
        'features/automation',
        'features/team-wiki-knowledge-base',
        'features/knowledge-base',
        'features/workspace-scripts',
      ],
    },
    {
      type: 'category',
      label: 'API 參考',
      items: [
        'api/manager-api',
        'api/runtime-api',
      ],
    },
    'acknowledgements',
  ],
};

export default sidebars;
