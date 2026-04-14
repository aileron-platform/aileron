/**
 * 檔案類型工具函數
 * 完全按照原始設計重構
 */

/**
 * 格式化檔案大小
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

/**
 * 格式化日期時間
 */
export const formatDateTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) {
    return '今天 ' + date.toLocaleTimeString('zh-TW', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  } else if (diffDays === 1) {
    return '昨天 ' + date.toLocaleTimeString('zh-TW', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  } else if (diffDays < 7) {
    return `${diffDays} 天前`;
  } else {
    return date.toLocaleDateString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
  }
};

/**
 * 檢查是否為隱藏檔案
 */
export const isHiddenFile = (fileName: string): boolean => {
  return fileName.startsWith('.');
};

/**
 * 檢查是否為圖片檔案
 */
export const isImageFile = (fileName: string): boolean => {
  const imageExtensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.bmp', '.tiff', '.svg'];
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return imageExtensions.includes(extension);
};

/**
 * 檢查是否為文字檔案
 */
export const isTextFile = (fileName: string): boolean => {
  const textExtensions = [
    '.txt', '.md', '.mdx', '.json', '.yaml', '.yml', '.toml', '.ini', '.conf',
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.scss', '.sass', '.less',
    '.html', '.htm', '.xml', '.svg', '.py', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.sh', '.bash',
    '.zsh', '.fish', '.ps1', '.sql', '.r', '.m', '.mm', '.pl', '.lua', '.vim',
    '.log', '.env', '.gitignore', '.gitattributes', '.dockerfile'
  ];
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return textExtensions.includes(extension);
};

/**
 * 檢查是否為程式碼檔案
 */
export const isCodeFile = (fileName: string): boolean => {
  const codeExtensions = [
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.scss', '.sass', '.less',
    '.html', '.htm', '.xml', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs',
    '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.sh', '.bash', '.zsh',
    '.fish', '.ps1', '.sql', '.r', '.m', '.mm', '.pl', '.lua', '.vim'
  ];
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return codeExtensions.includes(extension);
};

/**
 * 檢查是否為配置檔案
 */
export const isConfigFile = (fileName: string): boolean => {
  const configExtensions = ['.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.env'];
  const configFiles = [
    'package.json', 'tsconfig.json', 'vite.config.ts', 'vite.config.js',
    'tailwind.config.js', 'tailwind.config.ts', '.gitignore', '.gitattributes',
    'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', '.env', '.env.local',
    '.env.development', '.env.production'
  ];
  
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return configExtensions.includes(extension) || configFiles.includes(fileName);
};

/**
 * 檢查是否為壓縮檔案
 */
export const isArchiveFile = (fileName: string): boolean => {
  const archiveExtensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'];
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return archiveExtensions.includes(extension);
};

/**
 * 檢查是否為媒體檔案
 */
export const isMediaFile = (fileName: string): boolean => {
  const mediaExtensions = [
    // 圖片
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.bmp', '.tiff', '.svg',
    // 影片
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v',
    // 音訊
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'
  ];
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  return mediaExtensions.includes(extension);
};

/**
 * 獲取檔案的 MIME 類型
 */
export const getMimeType = (fileName: string): string => {
  const extension = fileName.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  
  const mimeMap: Record<string, string> = {
    // 文字檔案
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
    
    // 圖片檔案
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.svg': 'image/svg+xml',
    
    // 影片檔案
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
    '.webm': 'video/webm',
    '.mkv': 'video/x-matroska',
    
    // 音訊檔案
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.flac': 'audio/flac',
    '.aac': 'audio/aac',
    '.ogg': 'audio/ogg',
    '.wma': 'audio/x-ms-wma',
    
    // 其他檔案
    '.pdf': 'application/pdf',
    '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed',
    '.7z': 'application/x-7z-compressed',
    '.tar': 'application/x-tar',
    '.gz': 'application/gzip'
  };
  
  return mimeMap[extension] || 'application/octet-stream';
};

/**
 * 驗證檔案名稱是否有效
 */
export const isValidFileName = (fileName: string): boolean => {
  // 檢查是否為空或只有空白字元
  if (!fileName || fileName.trim().length === 0) {
    return false;
  }
  
  // 檢查是否包含非法字元 (Windows + Unix)
  const invalidChars = /[<>:"/\\|?*\x00-\x1f]/;
  if (invalidChars.test(fileName)) {
    return false;
  }
  
  // 檢查是否為保留名稱 (Windows)
  const reservedNames = [
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
  ];
  
  const nameWithoutExt = fileName.split('.')[0].toUpperCase();
  if (reservedNames.includes(nameWithoutExt)) {
    return false;
  }
  
  // 檢查長度限制 (大多數檔案系統限制為 255 字元)
  if (fileName.length > 255) {
    return false;
  }
  
  // 檢查是否以點或空格結尾 (Windows 不允許)
  if (fileName.endsWith('.') || fileName.endsWith(' ')) {
    return false;
  }
  
  return true;
};

/**
 * 清理檔案名稱，移除或替換非法字元
 */
export const sanitizeFileName = (fileName: string): string => {
  return fileName
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_') // 替換非法字元為底線
    .replace(/^\.+/, '') // 移除開頭的點
    .replace(/\.+$/, '') // 移除結尾的點
    .replace(/\s+$/, '') // 移除結尾的空格
    .substring(0, 255); // 限制長度
};
