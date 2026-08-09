import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: '系統架構說明',
      collapsed: false,
      items: [
        {
          type: 'category',
          label: '整體架構',
          collapsed: false,
          items: [
            'architecture/overview/index',
            'architecture/overview/identity-and-access',
            'architecture/overview/version-control',
            'architecture/overview/ai-chat',
            'architecture/overview/platform-resource-observability',
            'architecture/overview/execution-plane',
            {
              type: 'category',
              label: '網頁畫布（Canvas）',
              items: [
                'architecture/overview/canvas/protocol',
                'architecture/overview/canvas/publishing',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: '前端架構',
          items: [
            'architecture/frontend/index',
            'architecture/frontend/product-shell',
          ],
        },
        {
          type: 'category',
          label: '後端架構',
          items: [
            'architecture/backend/index',
            {
              type: 'category',
              label: 'workspace-manager',
              items: [
                'architecture/backend/workspace-manager/index',
                'architecture/backend/workspace-manager/identity-and-access',
              ],
            },
            {
              type: 'category',
              label: 'workspace-runtime',
              items: [
                'architecture/backend/workspace-runtime/index',
                'architecture/backend/workspace-runtime/agent-runtime-terminology',
              ],
            },
          ],
        },
      ],
    },
    {
      type: 'category',
      label: '功能說明',
      collapsed: false,
      items: [
        {
          type: 'category',
          label: '平台總覽',
          items: [
            'features/platform/index',
            'features/platform/permissions-and-roles',
            'features/platform/resource-statistics-and-capacity',
          ],
        },
        {
          type: 'category',
          label: '工作區',
          items: [
            'features/workspace/index',
            'features/workspace/lifecycle-and-access',
            'features/workspace/file-management',
            'features/workspace/version-control',
            {
              type: 'category',
              label: 'AI Agent',
              items: [
                'features/workspace/ai-agent/index',
                'features/workspace/ai-agent/ai-chat',
                'features/workspace/ai-agent/terminal',
              ],
            },
            {
              type: 'category',
              label: 'Agent 設定',
              items: [
                'features/workspace/agent-settings/index',
                'features/workspace/agent-settings/claude-code',
                'features/workspace/agent-settings/opencode',
                'features/workspace/agent-settings/codex',
              ],
            },
            'features/workspace/workspace-settings',
            'features/workspace/container-management',
            'features/workspace/automation-view',
            'features/workspace/browser',
            'features/workspace/preview',
            'features/workspace/scripts-and-sensitive-settings',
          ],
        },
        {
          type: 'category',
          label: '自動化中心',
          items: [
            'features/automation/index',
            'features/automation/jobs-and-triggers',
            'features/automation/executions',
          ],
        },
        {
          type: 'category',
          label: '應用市集（Marketplace）',
          items: [
            'features/marketplace/index',
            'features/marketplace/browse-and-install',
            'features/marketplace/author-and-publish',
            'features/marketplace/registry-and-governance',
          ],
        },
        {
          type: 'category',
          label: '知識庫中心',
          items: [
            'features/knowledge-base/index',
            'features/knowledge-base/files-and-version-control',
            'features/knowledge-base/sharing-and-permissions',
            'features/knowledge-base/usage-and-capacity',
          ],
        },
        {
          type: 'category',
          label: '使用者管理',
          items: [
            'features/user-management/index',
            'features/user-management/users',
            'features/user-management/groups',
            'features/user-management/roles-and-account-state',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: '安裝與維運',
      items: [
        'installation/getting-started',
        'installation/service-endpoints',
        'installation/docker',
        'installation/kubernetes',
        'installation/kubernetes-storage',
        'installation/kubernetes-images',
        'installation/kubernetes-networking',
        'installation/kubernetes-firewall',
        'installation/canvas-publishing',
        'installation/canvas-publishing-admin',
        'installation/canvas-publishing-user',
        'installation/environment-variables',
        'installation/oidc',
        'installation/production',
        'installation/troubleshooting',
        'installation/automation-runner-recovery',
      ],
    },
    {
      type: 'category',
      label: '參考資料',
      items: [
        {
          type: 'category',
          label: 'API 參考',
          items: ['api/manager-api', 'api/runtime-api'],
        },
        'reference/mcp-tools',
        'reference/helm-values',
        'reference/python-module-naming',
      ],
    },
    'acknowledgements',
  ],
};

export default sidebars;
