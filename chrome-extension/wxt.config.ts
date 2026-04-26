import { defineConfig } from "wxt";

export default defineConfig({
  manifest: {
    name: "Aileron",
    description: "Connect your browser to Aileron for automation control",
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
