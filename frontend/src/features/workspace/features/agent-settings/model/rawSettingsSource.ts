export interface RawSettingsScope {
  id: string;
  labelKey: string;
}

export interface RawSettingsSource {
  scopes: RawSettingsScope[];
  format: 'json' | 'toml';
  load(scopeId: string, signal?: AbortSignal): Promise<{ content: string }>;
  save(scopeId: string, content: string): Promise<void>;
}
