import { describe, expect, it } from "vitest";
import config from "../wxt.config";
import englishMessages from "../public/_locales/en/messages.json";
import traditionalChineseMessages from "../public/_locales/zh_TW/messages.json";

describe("extension manifest localization", () => {
  it("uses the localized description key and declares English as the default", async () => {
    const manifestFactory = config.manifest;
    expect(typeof manifestFactory).toBe("function");
    if (typeof manifestFactory !== "function") {
      return;
    }

    const manifest = await manifestFactory({} as never);
    expect(manifest.default_locale).toBe("en");
    expect(manifest.description).toBe("__MSG_extensionDescription__");
  });

  it("provides non-empty English and Traditional Chinese descriptions", () => {
    expect(englishMessages.extensionDescription.message).toBe(
      "Connect your browser to Aileron for automation control"
    );
    expect(traditionalChineseMessages.extensionDescription.message).toBe(
      "連接您的瀏覽器到 Aileron 以進行自動化控制"
    );
  });
});
