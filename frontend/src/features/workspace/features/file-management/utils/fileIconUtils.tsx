/**
 * 檔案圖示工具函數
 * 完全按照原始設計重構
 */

import React from 'react';
import {
  FileText,
  Folder,
  FolderOpen,
  File,
  Archive,
  Settings,
  Code,
  Database,
  FileImage,
  FileCode,
  FileSpreadsheet,
  FileVideo,
  FileAudio,
  Hash,
  Network
} from 'lucide-react';

// 檔案類型到圖示的映射
const FILE_ICON_MAP = {
  // 程式碼檔案
  typescript: <Code className="w-4 h-4 text-blue-500" />,
  javascript: <Code className="w-4 h-4 text-yellow-500" />,
  css: <FileCode className="w-4 h-4 text-blue-400" />,
  sass: <FileCode className="w-4 h-4 text-pink-500" />,
  less: <FileCode className="w-4 h-4 text-blue-600" />,
  stylus: <FileCode className="w-4 h-4 text-green-500" />,
  html: <FileCode className="w-4 h-4 text-orange-500" />,
  xml: <FileCode className="w-4 h-4 text-orange-400" />,
  svg: <FileImage className="w-4 h-4 text-purple-500" />,

  // 配置檔案
  json: <Settings className="w-4 h-4 text-yellow-600" />,
  yaml: <Settings className="w-4 h-4 text-red-500" />,
  toml: <Settings className="w-4 h-4 text-orange-600" />,
  config: <Settings className="w-4 h-4 text-gray-500" />,
  env: <Hash className="w-4 h-4 text-green-600" />,
  terraform: <Settings className="w-4 h-4 text-purple-600" />,
  ansible: <Settings className="w-4 h-4 text-red-600" />,

  // 腳本檔案
  shell: <FileCode className="w-4 h-4 text-green-600" />,
  powershell: <FileCode className="w-4 h-4 text-blue-600" />,
  
  // 文檔檔案
  markdown: <FileText className="w-4 h-4 text-blue-600" />,
  text: <FileText className="w-4 h-4 text-gray-600" />,
  log: <FileText className="w-4 h-4 text-gray-500" />,
  mermaid: <Network className="w-4 h-4 text-purple-600" />,
  drawio: <Network className="w-4 h-4 text-orange-600" />,
  
  // 媒體檔案
  image: <FileImage className="w-4 h-4 text-green-500" />,
  video: <FileVideo className="w-4 h-4 text-red-500" />,
  audio: <FileAudio className="w-4 h-4 text-purple-500" />,
  
  // 其他檔案
  pdf: <FileText className="w-4 h-4 text-red-600" />,
  archive: <Archive className="w-4 h-4 text-orange-500" />,
  database: <Database className="w-4 h-4 text-blue-700" />,
  spreadsheet: <FileSpreadsheet className="w-4 h-4 text-green-600" />,
  
  // 預設
  file: <File className="w-4 h-4 text-gray-500" />,
  directory: <Folder className="w-4 h-4 text-blue-500" />,
  directoryOpen: <FolderOpen className="w-4 h-4 text-blue-500" />
};

/**
 * 根據檔案名稱獲取對應的圖示
 */
export const getFileIcon = (fileName: string, isDirectory = false, isExpanded = false): React.ReactNode => {
  if (isDirectory) {
    return isExpanded ? FILE_ICON_MAP.directoryOpen : FILE_ICON_MAP.directory;
  }

  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  
  // 特殊檔案名稱處理
  const specialFiles: Record<string, keyof typeof FILE_ICON_MAP> = {
    'package.json': 'json',
    'tsconfig.json': 'json',
    'vite.config.ts': 'typescript',
    'vite.config.js': 'javascript',
    'tailwind.config.js': 'javascript',
    'tailwind.config.ts': 'typescript',
    '.env': 'env',
    '.env.local': 'env',
    '.env.development': 'env',
    '.env.production': 'env',
    'README.md': 'markdown',
    'CHANGELOG.md': 'markdown',
    'LICENSE': 'text',
    '.gitignore': 'config',
    '.gitattributes': 'config',
    'Dockerfile': 'config',
    'docker-compose.yml': 'yaml',
    'docker-compose.yaml': 'yaml',
    'ansible.cfg': 'ansible',
    'playbook.yml': 'ansible',
    'playbook.yaml': 'ansible'
  };

  if (specialFiles[fileName]) {
    return FILE_ICON_MAP[specialFiles[fileName]] || FILE_ICON_MAP.file;
  }

  // 根據副檔名判斷
  const extensionMap: Record<string, keyof typeof FILE_ICON_MAP> = {
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.css': 'css',
    '.scss': 'sass',
    '.sass': 'sass',
    '.less': 'less',
    '.styl': 'stylus',
    '.html': 'html',
    '.htm': 'html',
    '.xml': 'xml',
    '.svg': 'svg',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.tf': 'terraform',
    '.hcl': 'terraform',
    '.tfvars': 'terraform',
    '.ini': 'config',
    '.conf': 'config',
    '.sh': 'shell',
    '.bash': 'shell',
    '.zsh': 'shell',
    '.fish': 'shell',
    '.ps1': 'powershell',
    '.psm1': 'powershell',
    '.psd1': 'powershell',
    '.md': 'markdown',
    '.mdx': 'markdown',
    '.mmd': 'mermaid',
    '.mermaid': 'mermaid',
    '.drawio': 'drawio',
    '.dio': 'drawio',
    '.txt': 'text',
    '.log': 'log',
    '.png': 'image',
    '.jpg': 'image',
    '.jpeg': 'image',
    '.gif': 'image',
    '.webp': 'image',
    '.ico': 'image',
    '.bmp': 'image',
    '.tiff': 'image',
    '.mp4': 'video',
    '.avi': 'video',
    '.mov': 'video',
    '.wmv': 'video',
    '.flv': 'video',
    '.webm': 'video',
    '.mp3': 'audio',
    '.wav': 'audio',
    '.flac': 'audio',
    '.aac': 'audio',
    '.ogg': 'audio',
    '.pdf': 'pdf',
    '.zip': 'archive',
    '.rar': 'archive',
    '.7z': 'archive',
    '.tar': 'archive',
    '.gz': 'archive',
    '.bz2': 'archive',
    '.xz': 'archive',
    '.sql': 'database',
    '.db': 'database',
    '.sqlite': 'database',
    '.xlsx': 'spreadsheet',
    '.xls': 'spreadsheet',
    '.csv': 'spreadsheet',
    '.ods': 'spreadsheet'
  };

  const iconType = extensionMap[extension];
  return FILE_ICON_MAP[iconType] || FILE_ICON_MAP.file;
};

/**
 * 根據檔案名稱獲取程式語言類型
 */
export const getFileLanguage = (fileName: string): string => {
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  const lowerFileName = fileName.toLowerCase();

  // 特殊檔案名稱處理 (Ansible)
  if (lowerFileName === 'ansible.cfg' ||
      lowerFileName.includes('playbook') ||
      lowerFileName.includes('inventory') ||
      lowerFileName.includes('hosts.yml') ||
      lowerFileName.includes('hosts.yaml')) {
    return 'Ansible';
  }

  const languageMap: Record<string, string> = {
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript React',
    '.js': 'JavaScript',
    '.jsx': 'JavaScript React',
    '.mjs': 'JavaScript Module',
    '.cjs': 'JavaScript CommonJS',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'Sass',
    '.less': 'Less',
    '.styl': 'Stylus',
    '.html': 'HTML',
    '.htm': 'HTML',
    '.xml': 'XML',
    '.svg': 'SVG',
    '.json': 'JSON',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.toml': 'TOML',
    '.tf': 'Terraform',
    '.hcl': 'HCL',
    '.tfvars': 'Terraform Variables',
    '.md': 'Markdown',
    '.mdx': 'MDX',
    '.mmd': 'Mermaid',
    '.mermaid': 'Mermaid',
    '.drawio': 'Draw.io',
    '.dio': 'Draw.io',
    '.txt': 'Plain Text',
    '.log': 'Log File',
    '.py': 'Python',
    '.java': 'Java',
    '.c': 'C',
    '.cpp': 'C++',
    '.h': 'C Header',
    '.hpp': 'C++ Header',
    '.cs': 'C#',
    '.php': 'PHP',
    '.rb': 'Ruby',
    '.go': 'Go',
    '.rs': 'Rust',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.scala': 'Scala',
    '.sh': 'Shell Script',
    '.bash': 'Bash Script',
    '.zsh': 'Zsh Script',
    '.fish': 'Fish Script',
    '.ps1': 'PowerShell',
    '.psm1': 'PowerShell Module',
    '.psd1': 'PowerShell Data',
    '.sql': 'SQL',
    '.r': 'R',
    '.m': 'Objective-C',
    '.mm': 'Objective-C++',
    '.pl': 'Perl',
    '.lua': 'Lua',
    '.vim': 'Vim Script',
    '.dockerfile': 'Dockerfile',
    '.gitignore': 'Git Ignore',
    '.env': 'Environment'
  };

  return languageMap[extension] || 'Unknown';
};

/**
 * 檢查是否為 Mermaid 檔案
 */
export const isMermaidFile = (fileName: string): boolean => {
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return extension === '.mmd' || extension === '.mermaid';
};

/**
 * 檢查是否為 Markdown 檔案
 */
export const isMarkdownFile = (fileName: string): boolean => {
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return extension === '.md' || extension === '.mdx';
};

/**
 * 檢查是否為 Draw.io 檔案
 */
export const isDrawioFile = (fileName: string): boolean => {
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return extension === '.drawio' || extension === '.dio';
};
