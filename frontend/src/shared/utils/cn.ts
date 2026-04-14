/**
 * cn - 類名合併工具函數
 * 
 * 基於 clsx 和 tailwind-merge 的類名合併工具
 */

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
