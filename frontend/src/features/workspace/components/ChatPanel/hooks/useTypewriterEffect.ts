/**
 * useTypewriterEffect - 打字機效果 Hook
 *
 * 在指定時間內逐字顯示文字，支持循環顯示不同的隨機單字
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getRandomTypingVerb } from '../constants/typingVerbs';

interface UseTypewriterEffectOptions {
  /**
   * 完成打字的總時間（毫秒）
   * @default 1000
   */
  duration?: number;

  /**
   * 是否循環顯示（打完一個單字後自動選擇下一個）
   * @default false
   */
  loop?: boolean;
}

interface UseTypewriterEffectResult {
  /**
   * 當前顯示的文字
   */
  displayedText: string;

  /**
   * 是否正在打字中
   */
  isTyping: boolean;
}

/**
 * 打字機效果 Hook
 *
 * @example
 * ```tsx
 * const { displayedText, isTyping } = useTypewriterEffect({
 *   duration: 1000,
 *   loop: true
 * });
 * ```
 */
export function useTypewriterEffect({
  duration = 1000,
  loop = false,
}: UseTypewriterEffectOptions = {}): UseTypewriterEffectResult {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(true);
  const [currentVerb, setCurrentVerb] = useState(() => getRandomTypingVerb());

  const startTimeRef = useRef<number>(0);
  const animationFrameRef = useRef<number | null>(null);
  const pauseTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 選擇新的隨機單字
  const selectNewVerb = useCallback(() => {
    let newVerb = getRandomTypingVerb();
    // 確保不會連續兩次顯示相同的單字
    while (newVerb === currentVerb) {
      newVerb = getRandomTypingVerb();
    }
    setCurrentVerb(newVerb);
  }, [currentVerb]);

  useEffect(() => {
    // 重置狀態
    setDisplayedText('');
    setIsTyping(true);
    startTimeRef.current = Date.now();

    const textLength = currentVerb.length;

    // 使用 requestAnimationFrame 實現平滑的打字效果
    const animate = () => {
      const elapsed = Date.now() - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // 計算當前應該顯示的字符數
      const currentLength = Math.floor(progress * textLength);
      setDisplayedText(currentVerb.slice(0, currentLength));

      // 如果還沒完成，繼續動畫
      if (progress < 1) {
        animationFrameRef.current = requestAnimationFrame(animate);
      } else {
        // 打字完成
        setIsTyping(false);

        // 如果啟用循環，短暫暫停後選擇新單字
        if (loop) {
          pauseTimeoutRef.current = setTimeout(() => {
            selectNewVerb();
          }, 1000); // 暫停 300ms 後開始下一個單字
        }
      }
    };

    // 開始動畫
    animationFrameRef.current = requestAnimationFrame(animate);

    // 清理函數
    return () => {
      const currentAnimationFrame = animationFrameRef.current;
      const currentPauseTimeout = pauseTimeoutRef.current;

      if (currentAnimationFrame) {
        cancelAnimationFrame(currentAnimationFrame);
      }
      if (currentPauseTimeout) {
        clearTimeout(currentPauseTimeout);
      }
    };
  }, [currentVerb, duration, loop, selectNewVerb]);

  return { displayedText, isTyping };
}

