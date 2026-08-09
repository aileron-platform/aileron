import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Aileron',
  tagline: '可管理、可擴充的 AI 開發工作區平台',
  favicon: 'img/favicon.ico',

  url: 'https://aileron-platform.github.io',
  baseUrl: '/aileron/',

  organizationName: 'aileron-platform',
  projectName: 'aileron',
  trailingSlash: false,

  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  i18n: {
    defaultLocale: 'zh-Hant',
    locales: ['zh-Hant', 'en'],
    localeConfigs: {
      'zh-Hant': {
        label: '繁體中文',
      },
      en: {
        label: 'English',
      },
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themes: ['@docusaurus/theme-mermaid'],

  themeConfig: {
    colorMode: {
      defaultMode: 'light',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Aileron',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: '文件',
        },
        {
          to: '/api/manager-api',
          label: 'Manager API',
          position: 'right',
        },
        {
          to: '/api/runtime-api',
          label: 'Runtime API',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: '文件',
          items: [
            { label: '安裝說明', to: '/installation/getting-started' },
            { label: '部署與環境', to: '/installation/docker' },
            { label: '系統架構說明', to: '/architecture/overview/' },
          ],
        },
        {
          title: 'API',
          items: [
            { label: 'Manager API', to: '/api/manager-api' },
            { label: 'Runtime API', to: '/api/runtime-api' },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Aileron`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'yaml', 'python', 'typescript', 'docker'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
