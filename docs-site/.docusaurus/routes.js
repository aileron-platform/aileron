import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/aileron/__docusaurus/debug',
    component: ComponentCreator('/aileron/__docusaurus/debug', '753'),
    exact: true
  },
  {
    path: '/aileron/__docusaurus/debug/config',
    component: ComponentCreator('/aileron/__docusaurus/debug/config', '4f7'),
    exact: true
  },
  {
    path: '/aileron/__docusaurus/debug/content',
    component: ComponentCreator('/aileron/__docusaurus/debug/content', 'a5a'),
    exact: true
  },
  {
    path: '/aileron/__docusaurus/debug/globalData',
    component: ComponentCreator('/aileron/__docusaurus/debug/globalData', '7ca'),
    exact: true
  },
  {
    path: '/aileron/__docusaurus/debug/metadata',
    component: ComponentCreator('/aileron/__docusaurus/debug/metadata', '0e8'),
    exact: true
  },
  {
    path: '/aileron/__docusaurus/debug/registry',
    component: ComponentCreator('/aileron/__docusaurus/debug/registry', '98e'),
    exact: true
  },
  {
    path: '/aileron/__docusaurus/debug/routes',
    component: ComponentCreator('/aileron/__docusaurus/debug/routes', '35f'),
    exact: true
  },
  {
    path: '/aileron/',
    component: ComponentCreator('/aileron/', '44a'),
    routes: [
      {
        path: '/aileron/',
        component: ComponentCreator('/aileron/', 'a7b'),
        routes: [
          {
            path: '/aileron/',
            component: ComponentCreator('/aileron/', 'f72'),
            routes: [
              {
                path: '/aileron/acknowledgements',
                component: ComponentCreator('/aileron/acknowledgements', '1ad'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/api/manager-api',
                component: ComponentCreator('/aileron/api/manager-api', 'b20'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/api/runtime-api',
                component: ComponentCreator('/aileron/api/runtime-api', 'aa8'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/architecture/overview',
                component: ComponentCreator('/aileron/architecture/overview', '44c'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/architecture/workspace-manager',
                component: ComponentCreator('/aileron/architecture/workspace-manager', '462'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/architecture/workspace-runtime',
                component: ComponentCreator('/aileron/architecture/workspace-runtime', 'bb1'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/deployment/docker',
                component: ComponentCreator('/aileron/deployment/docker', 'f2b'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/deployment/environment-variables',
                component: ComponentCreator('/aileron/deployment/environment-variables', 'c4b'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/deployment/keycloak',
                component: ComponentCreator('/aileron/deployment/keycloak', 'b01'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/deployment/kubernetes',
                component: ComponentCreator('/aileron/deployment/kubernetes', '3d8'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/deployment/production',
                component: ComponentCreator('/aileron/deployment/production', '288'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/deployment/troubleshooting',
                component: ComponentCreator('/aileron/deployment/troubleshooting', 'a41'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/features/automation',
                component: ComponentCreator('/aileron/features/automation', 'b58'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/features/claude-integration',
                component: ComponentCreator('/aileron/features/claude-integration', 'b05'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/features/openspec',
                component: ComponentCreator('/aileron/features/openspec', '653'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/features/workspace-lifecycle',
                component: ComponentCreator('/aileron/features/workspace-lifecycle', '807'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/quick-start/installation',
                component: ComponentCreator('/aileron/quick-start/installation', '613'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/quick-start/services',
                component: ComponentCreator('/aileron/quick-start/services', 'dda'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/aileron/',
                component: ComponentCreator('/aileron/', 'ce9'),
                exact: true,
                sidebar: "docsSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
