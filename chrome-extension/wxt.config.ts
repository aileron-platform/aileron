import { defineConfig } from "wxt";

export default defineConfig({
  manifest: {
    name: "Aileron",
    description: "連接您的瀏覽器到 Aileron 以進行自動化控制",
    permissions: ["debugger", "tabGroups", "storage", "alarms", "scripting"],
    host_permissions: ["<all_urls>"],
    icons: {
      16: "icons/icon-16.png",
      32: "icons/icon-32.png",
      48: "icons/icon-48.png",
      128: "icons/icon-128.png",
    },
  },
});
