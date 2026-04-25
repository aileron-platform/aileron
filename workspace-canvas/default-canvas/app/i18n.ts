export type Locale = "en" | "zh-TW";

export interface Translation {
  title: string;
  descBefore: string; // text before <code>/workspace</code>
  descAfter: string;  // text after <code>/workspace</code>
  quickStart: string;
}

export const translations: Record<Locale, Translation> = {
  en: {
    title: "Canvas Runtime",
    descBefore: "No Canvas route manifest or renderable app detected in the workspace. Create content in",
    descAfter: "and click the Sync button to start Canvas.",
    quickStart: "Quick Start:",
  },
  "zh-TW": {
    title: "Canvas Runtime",
    descBefore: "工作區內尚未偵測到 Canvas route manifest 或可呈現的應用。請在",
    descAfter: "建立內容，再點擊 Sync 按鈕即可啟動 Canvas。",
    quickStart: "快速建立：",
  },
};

export function resolveLocale(lang: string | null): Locale {
  if (lang === "en") return "en";
  return "zh-TW";
}
