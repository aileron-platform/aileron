/**
 * ACP raw payload helper utilities.
 *
 * Goal: prefer raw ACP tool_call/tool_call_update payloads without relying on backend-mapped fields.
 */

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);

const asRecord = (value: unknown): Record<string, unknown> | null =>
  (isRecord(value) ? value : null);

const asRecordArray = (value: unknown): Record<string, unknown>[] => {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => isRecord(item));
};

const firstString = (...values: Array<unknown>): string => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
};

export const extractTextFromAcpNode = (node: unknown): string => {
  if (typeof node === 'string') return node;
  if (Array.isArray(node)) {
    return node.map((item) => extractTextFromAcpNode(item)).filter(Boolean).join('\n');
  }
  if (!isRecord(node)) return '';

  return firstString(
    node.text,
    extractTextFromAcpNode(node.content),
    extractTextFromAcpNode(node.output),
    extractTextFromAcpNode(node.message),
  );
};

export const extractAcpContentNodes = (value: unknown): Record<string, unknown>[] => {
  if (Array.isArray(value)) return asRecordArray(value);

  const record = asRecord(value);
  if (!record) return [];

  return asRecordArray(record.content);
};

export const extractAcpLocations = (input?: Record<string, unknown>): Record<string, unknown>[] => {
  if (!input) return [];

  return asRecordArray(input.locations);
};

export const extractAcpKind = (input?: Record<string, unknown>): string =>
  firstString(input?.kind);

export const extractAcpTitle = (input?: Record<string, unknown>, fallback = ''): string =>
  firstString(input?.title, fallback);

const extractPathFromTitle = (title: string): string => {
  const normalized = title.toLowerCase();
  const prefixes = [
    'writing to ',
    'write to ',
    'editing ',
    'updating ',
    'reading ',
    'read ',
    'deleting ',
    'moving ',
  ];

  for (const prefix of prefixes) {
    if (normalized.startsWith(prefix)) {
      return title.slice(prefix.length).trim();
    }
  }

  return '';
};

export const extractAcpPath = (
  input: Record<string, unknown> | undefined,
  output: unknown,
  toolName: string
): string => {
  const locations = extractAcpLocations(input);
  const locationPath = firstString(locations[0]?.path);
  if (locationPath) return locationPath;

  const contentNodes = extractAcpContentNodes(output);
  const diffNode = contentNodes.find((item) => item.type === 'diff') ||
    contentNodes.find((item) => typeof item.newText === 'string' || typeof item.oldText === 'string');

  if (diffNode) {
    const diffPath = firstString(diffNode.path);
    if (diffPath) return diffPath;
  }

  const inputPath = firstString(
    input?.path,
    input?.file_path,
    input?.filePath,
    input?.target
  );
  if (inputPath) return inputPath;

  return extractPathFromTitle(extractAcpTitle(input, toolName));
};

export const extractAcpCommand = (
  input: Record<string, unknown> | undefined,
  toolName: string
): string => {
  const fromInput = firstString(input?.command, input?.cmd, input?.script);
  if (fromInput) return fromInput;

  return extractAcpTitle(input, toolName);
};

export const extractAcpDiff = (output: unknown): Record<string, unknown> | null => {
  const contentNodes = extractAcpContentNodes(output);
  for (const node of contentNodes) {
    if (node.type === 'diff') return node;
    if (typeof node.oldText === 'string' || typeof node.newText === 'string') return node;
  }
  return null;
};

export const extractAcpOutputText = (output: unknown): string => {
  if (typeof output === 'string') return output;

  if (Array.isArray(output)) {
    return output.map((item) => extractTextFromAcpNode(item)).filter(Boolean).join('\n');
  }

  if (!isRecord(output)) return '';

  const fromContentNodes = extractAcpContentNodes(output)
    .map((node) => extractTextFromAcpNode(node))
    .filter(Boolean)
    .join('\n');
  if (fromContentNodes) return fromContentNodes;

  return firstString(
    output.stdout,
    output.output,
    output.content,
    output.message,
    output.error_message,
    output.error,
  );
};

export const extractAcpErrorText = (output: unknown): string => {
  if (typeof output === 'string') return output;
  const outputRecord = asRecord(output);
  if (!outputRecord) return '';

  return firstString(
    outputRecord.error_message,
    outputRecord.error,
    outputRecord.message,
  );
};
