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
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
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
          href: 'http://localhost:3001/docs',
          label: 'Manager API',
          position: 'right',
        },
        {
          href: 'http://localhost:3002/docs',
          label: 'Runtime API',
          position: 'right',
        },
        {
          type: 'localeDropdown',
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
            { label: '快速開始', to: '/quick-start/installation' },
            { label: '部署說明', to: '/deployment/docker' },
            { label: '架構概覽', to: '/architecture/overview' },
          ],
        },
        {
          title: 'API',
          items: [
            { label: 'Manager API (Swagger)', href: 'http://localhost:3001/docs' },
            { label: 'Runtime API (Swagger)', href: 'http://localhost:3002/docs' },
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
