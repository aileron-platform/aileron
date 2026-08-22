export type Locale = "en" | "zh-TW";

export interface Translation {
  eyebrow: string;
  title: string;
  description: string;
  status: string;
  outcomeLabel: string;
  outcomeDescription: string;
  contentLabel: string;
  contentDescription: string;
  syncLabel: string;
  syncDescription: string;
  promptLabel: string;
  promptType: string;
  promptExample: string;
  footer: string;
}

export const translations: Record<Locale, Translation> = {
  en: {
    eyebrow: "Workspace Canvas / standby",
    title: "Your next canvas starts with a skill.",
    description: "Ask your AI agent to use the aileron-web-canvas skill. It will create the experience in your workspace and prepare it for live preview.",
    status: "Runtime online",
    outcomeLabel: "Describe the outcome",
    outcomeDescription: "Tell the agent what you want to create, who it is for, and the visual direction.",
    contentLabel: "Use the Canvas skill",
    contentDescription: "Ask the agent to use aileron-web-canvas to build the page and register its preview routes.",
    syncLabel: "Review the result",
    syncDescription: "When the skill finishes, review the generated experience here and send visual feedback to the agent.",
    promptLabel: "Prompt starter",
    promptType: "Prompt",
    promptExample: "Use the aileron-web-canvas skill to create a responsive product overview page with a focused editorial style.",
    footer: "The skill owns the Canvas files, manifest, and preview setup inside the workspace.",
  },
  "zh-TW": {
    eyebrow: "工作區畫布 / 待命中",
    title: "下一張畫布，從一個 Skill 開始。",
    description: "請 AI Agent 使用 aileron-web-canvas skill，它會在工作區建立完整內容，並準備好即時預覽。",
    status: "Runtime 已上線",
    outcomeLabel: "描述預期成果",
    outcomeDescription: "告訴 Agent 想建立的內容、使用對象與視覺方向。",
    contentLabel: "使用 Canvas Skill",
    contentDescription: "請 Agent 使用 aileron-web-canvas 建立頁面並註冊預覽路由。",
    syncLabel: "檢視產生結果",
    syncDescription: "Skill 完成後，直接在此檢視成品，並將畫面修改意見送回 Agent。",
    promptLabel: "Prompt 範例",
    promptType: "Prompt",
    promptExample: "請使用 aileron-web-canvas skill，建立一個響應式產品介紹頁，採用聚焦且具有編輯感的視覺風格。",
    footer: "Canvas 檔案、manifest 與預覽設定都由 skill 在工作區內完成。",
  },
};

export function resolveLocale(lang: string | null): Locale {
  if (lang === "en") return "en";
  return "zh-TW";
}
