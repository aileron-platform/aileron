import type { ConfigureBrowserExtensionPairingMessage } from "./types";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function parseTrustedFrontendOrigins(raw: string | undefined): string[] {
  if (raw === undefined || raw === "") {
    return [];
  }
  if (raw !== raw.trim()) {
    throw new Error("Trusted frontend origins must not contain outer whitespace");
  }

  const origins = raw.split(",").map((entry) => {
    if (entry === "" || entry !== entry.trim() || entry.includes("*")) {
      throw new Error("Trusted frontend origin is invalid");
    }
    let url: URL;
    try {
      url = new URL(entry);
    } catch {
      throw new Error("Trusted frontend origin is invalid");
    }
    if (
      url.username !== "" ||
      url.password !== "" ||
      url.search !== "" ||
      url.hash !== "" ||
      url.pathname !== "/" ||
      (url.protocol !== "https:" &&
        !(url.protocol === "http:" && LOOPBACK_HOSTS.has(url.hostname)))
    ) {
      throw new Error("Trusted frontend origin is invalid");
    }
    if (entry !== url.origin && entry !== `${url.origin}/`) {
      throw new Error("Trusted frontend origin must be canonical");
    }
    return url.origin;
  });

  if (new Set(origins).size !== origins.length) {
    throw new Error("Trusted frontend origins must be unique");
  }
  return origins;
}

export function toExternallyConnectableMatches(origins: string[]): string[] {
  return Array.from(
    new Set(
      origins.map((origin) => {
        const url = new URL(origin);
        return `${url.protocol}//${url.hostname}/*`;
      })
    )
  );
}

export function isTrustedFrontendSender(
  senderUrl: string | undefined,
  trustedOrigins: string[]
): boolean {
  if (!senderUrl) {
    return false;
  }
  try {
    const url = new URL(senderUrl);
    return (
      url.username === "" &&
      url.password === "" &&
      trustedOrigins.includes(url.origin)
    );
  } catch {
    return false;
  }
}

export function isConfigureBrowserExtensionPairingMessage(
  value: unknown
): value is ConfigureBrowserExtensionPairingMessage {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const message = value as Record<string, unknown>;
  if (
    message.type !== "configureBrowserExtensionPairing" ||
    typeof message.pairing !== "object" ||
    message.pairing === null
  ) {
    return false;
  }
  const pairing = message.pairing as Record<string, unknown>;
  return (
    Object.keys(message).every((key) => key === "type" || key === "pairing") &&
    Object.keys(pairing).every(
      (key) => key === "assertion" || key === "runtimeInstanceId"
    ) &&
    typeof pairing.assertion === "string" &&
    typeof pairing.runtimeInstanceId === "string"
  );
}
