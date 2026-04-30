export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export const isHiddenFile = (fileName: string): boolean => fileName.startsWith('.');

const getExtension = (fileName: string): string => fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';

export const isImageFile = (fileName: string): boolean => {
  const imageExtensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.bmp', '.tiff', '.svg'];
  return imageExtensions.includes(getExtension(fileName));
};

export const isTextFile = (fileName: string): boolean => {
  const textExtensions = [
    '.txt', '.md', '.mdx', '.json', '.yaml', '.yml', '.toml', '.ini', '.conf',
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.scss', '.sass', '.less',
    '.html', '.htm', '.xml', '.svg', '.py', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.sh', '.bash',
    '.zsh', '.fish', '.ps1', '.sql', '.r', '.m', '.mm', '.pl', '.lua', '.vim',
    '.log', '.env', '.gitignore', '.gitattributes', '.dockerfile',
  ];
  return textExtensions.includes(getExtension(fileName));
};

export const isCodeFile = (fileName: string): boolean => {
  const codeExtensions = [
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.scss', '.sass', '.less',
    '.html', '.htm', '.xml', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs',
    '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.sh', '.bash', '.zsh',
    '.fish', '.ps1', '.sql', '.r', '.m', '.mm', '.pl', '.lua', '.vim',
  ];
  return codeExtensions.includes(getExtension(fileName));
};

export const isConfigFile = (fileName: string): boolean => {
  const configExtensions = ['.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.env'];
  const configFiles = [
    'package.json', 'tsconfig.json', 'vite.config.ts', 'vite.config.js',
    'tailwind.config.js', 'tailwind.config.ts', '.gitignore', '.gitattributes',
    'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', '.env', '.env.local',
    '.env.development', '.env.production',
  ];

  return configExtensions.includes(getExtension(fileName)) || configFiles.includes(fileName);
};

export const isArchiveFile = (fileName: string): boolean => {
  const archiveExtensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'];
  return archiveExtensions.includes(getExtension(fileName));
};

export const isMediaFile = (fileName: string): boolean => {
  const mediaExtensions = [
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.bmp', '.tiff', '.svg',
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v',
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
  ];
  return mediaExtensions.includes(getExtension(fileName));
};

export const getMimeType = (fileName: string): string => {
  const mimeMap: Record<string, string> = {
    '.txt': 'text/plain',
    '.md': 'text/markdown',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.ts': 'text/typescript',
    '.json': 'application/json',
    '.xml': 'text/xml',
    '.yaml': 'text/yaml',
    '.yml': 'text/yaml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.svg': 'image/svg+xml',
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
    '.webm': 'video/webm',
    '.mkv': 'video/x-matroska',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.flac': 'audio/flac',
    '.aac': 'audio/aac',
    '.ogg': 'audio/ogg',
    '.wma': 'audio/x-ms-wma',
    '.pdf': 'application/pdf',
    '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed',
    '.7z': 'application/x-7z-compressed',
    '.tar': 'application/x-tar',
    '.gz': 'application/gzip',
  };

  return mimeMap[getExtension(fileName)] || 'application/octet-stream';
};

export const isValidFileName = (fileName: string): boolean => {
  if (!fileName || fileName.trim().length === 0) return false;
  if (/[<>:"/\\|?*\x00-\x1f]/.test(fileName)) return false;

  const reservedNames = [
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
  ];
  const nameWithoutExt = fileName.split('.')[0].toUpperCase();

  return !reservedNames.includes(nameWithoutExt)
    && fileName.length <= 255
    && !fileName.endsWith('.')
    && !fileName.endsWith(' ');
};

export const sanitizeFileName = (fileName: string): string => (
  fileName
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')
    .replace(/^\.+/, '')
    .replace(/\.+$/, '')
    .replace(/\s+$/, '')
    .substring(0, 255)
);
