/**
 * 檔案操作工具函數
 */

/**
 * 下載檔案
 */
export function downloadFile(content: string, fileName: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * 複製文字到剪貼簿
 */
export async function copyToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

/**
 * 判斷是否為 Markdown 檔案
 */
export function isMarkdownFile(filename: string): boolean {
  return filename.toLowerCase().endsWith('.md');
}

/**
 * 取得檔案副檔名
 */
export function getFileExtension(filename: string): string {
  return filename.split('.').pop() || '';
}

/**
 * 取得檔案名稱（不含副檔名）
 */
export function getFileNameWithoutExtension(filename: string): string {
  const parts = filename.split('.');
  if (parts.length === 1) return filename;
  return parts.slice(0, -1).join('.');
}

/**
 * 格式化檔案大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

