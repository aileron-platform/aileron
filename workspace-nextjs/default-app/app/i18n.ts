export type Locale = "en" | "zh-TW";

export interface Translation {
  title: string;
  descBefore: string; // text before <code>/workspace</code>
  descAfter: string;  // text after <code>/workspace</code>
  quickStart: string;
}

export const translations: Record<Locale, Translation> = {
  en: {
    title: "Next.js Project Preview",
    descBefore: "No Next.js project detected in the workspace. Create a project in",
    descAfter: "and click the Sync button to start previewing.",
    quickStart: "Quick Start:",
  },
  "zh-TW": {
    title: "Next.js 專案預覽",
    descBefore: "工作區內尚未偵測到 Next.js 專案。請在",
    descAfter: "建立專案，再點擊 Sync 按鈕即可開始預覽。",
    quickStart: "快速建立：",
  },
};

export function resolveLocale(lang: string | null): Locale {
  if (lang === "en") return "en";
  return "zh-TW";
}
