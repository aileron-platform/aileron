import { defineConfig } from "wxt";
import {
  parseTrustedFrontendOrigins,
  toExternallyConnectableMatches,
} from "./utils/trustedFrontendOrigins";

export default defineConfig({
  manifest: () => {
    const trustedOrigins = parseTrustedFrontendOrigins(
      process.env.WXT_TRUSTED_FRONTEND_ORIGINS
    );
    return {
      name: "Aileron",
      default_locale: "en",
      description: "__MSG_extensionDescription__",
      permissions: ["debugger", "tabGroups", "storage", "alarms", "scripting"],
      host_permissions: ["<all_urls>"],
      ...(trustedOrigins.length > 0
        ? {
            externally_connectable: {
              matches: toExternallyConnectableMatches(trustedOrigins),
            },
          }
        : {}),
      icons: {
        16: "icons/icon-16.png",
        32: "icons/icon-32.png",
        48: "icons/icon-48.png",
        128: "icons/icon-128.png",
      },
    };
  },
});
