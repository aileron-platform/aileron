const CHROME_EXTENSION_ID_PATTERN = /^[a-p]{32}$/;

export function resolveBrowserExtensionId(
  rawValue: string | undefined = import.meta.env.VITE_BROWSER_EXTENSION_ID
): string | null {
  if (!rawValue || !CHROME_EXTENSION_ID_PATTERN.test(rawValue)) {
    return null;
  }
  return rawValue;
}
