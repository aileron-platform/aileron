import { describe, expect, it } from "vitest";
import {
  isConfigureBrowserExtensionPairingMessage,
  isTrustedFrontendSender,
  parseTrustedFrontendOrigins,
  toExternallyConnectableMatches,
} from "../utils/trustedFrontendOrigins";

describe("trusted frontend origins", () => {
  it("accepts canonical HTTPS and loopback HTTP origins", () => {
    const origins = parseTrustedFrontendOrigins(
      "https://app.example.com,http://localhost:8082,http://127.0.0.1:8082"
    );

    expect(origins).toEqual([
      "https://app.example.com",
      "http://localhost:8082",
      "http://127.0.0.1:8082",
    ]);
    expect(toExternallyConnectableMatches(origins)).toEqual([
      "https://app.example.com/*",
      "http://localhost/*",
      "http://127.0.0.1/*",
    ]);
  });

  it.each([
    " http://localhost:8082",
    "http://example.com",
    "https://*.example.com",
    "https://user@example.com",
    "https://example.com/path",
    "https://example.com?debug=1",
    "https://EXAMPLE.com",
    "https://example.com,https://example.com/",
  ])("rejects unsafe or non-canonical origin %s", (value) => {
    expect(() => parseTrustedFrontendOrigins(value)).toThrow();
  });

  it("matches the exact sender origin including its port", () => {
    const trusted = ["http://localhost:8082"];

    expect(
      isTrustedFrontendSender("http://localhost:8082/workspaces/one", trusted)
    ).toBe(true);
    expect(
      isTrustedFrontendSender("http://localhost:3000/workspaces/one", trusted)
    ).toBe(false);
    expect(isTrustedFrontendSender(undefined, trusted)).toBe(false);
  });

  it("accepts only the narrow pairing message shape", () => {
    expect(
      isConfigureBrowserExtensionPairingMessage({
        type: "configureBrowserExtensionPairing",
        pairing: {
          assertion: "header.payload.signature",
          runtimeInstanceId: "runtime-one",
        },
      })
    ).toBe(true);
    expect(
      isConfigureBrowserExtensionPairingMessage({
        type: "configureBrowserExtensionPairing",
        pairing: {
          assertion: "header.payload.signature",
          runtimeInstanceId: "runtime-one",
          token: "legacy",
        },
      })
    ).toBe(false);
  });
});
