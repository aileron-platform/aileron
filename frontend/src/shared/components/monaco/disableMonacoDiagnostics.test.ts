import { beforeEach, describe, expect, it, vi } from 'vitest';

const createDiagnosticsDefaults = (options: Record<string, unknown>) => ({
  getDiagnosticsOptions: vi.fn(() => options),
  setDiagnosticsOptions: vi.fn(),
});

const createLanguageDefaults = (options: Record<string, unknown>) => ({
  getOptions: vi.fn(() => options),
  setOptions: vi.fn(),
});

const importFreshModule = async () => {
  vi.resetModules();
  return import('./disableMonacoDiagnostics');
};

describe('disableMonacoDiagnostics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('disables validation diagnostics while preserving existing language options', async () => {
    const { disableMonacoDiagnostics } = await importFreshModule();
    const typescriptDefaults = createDiagnosticsDefaults({ compilerOptions: { strict: true } });
    const javascriptDefaults = createDiagnosticsDefaults({ allowNonTsExtensions: true });
    const jsonDefaults = createDiagnosticsDefaults({ schemas: [] });
    const cssDefaults = createLanguageDefaults({ lint: { emptyRules: 'ignore' } });
    const scssDefaults = createLanguageDefaults({ lint: { unknownProperties: 'warning' } });
    const lessDefaults = createLanguageDefaults({ lint: { zeroUnits: 'ignore' } });
    const htmlDefaults = createLanguageDefaults({ format: { wrapLineLength: 120 } });

    disableMonacoDiagnostics({
      languages: {
        typescript: {
          typescriptDefaults,
          javascriptDefaults,
        },
        json: { jsonDefaults },
        css: {
          cssDefaults,
          scssDefaults,
          lessDefaults,
        },
        html: { htmlDefaults },
      },
      editor: {
        getModels: vi.fn(() => []),
        onDidCreateModel: vi.fn(),
        setModelMarkers: vi.fn(),
      },
    });

    expect(typescriptDefaults.setDiagnosticsOptions).toHaveBeenCalledWith({
      compilerOptions: { strict: true },
      noSemanticValidation: true,
      noSyntaxValidation: true,
      noSuggestionDiagnostics: true,
    });
    expect(javascriptDefaults.setDiagnosticsOptions).toHaveBeenCalledWith({
      allowNonTsExtensions: true,
      noSemanticValidation: true,
      noSyntaxValidation: true,
      noSuggestionDiagnostics: true,
    });
    expect(jsonDefaults.setDiagnosticsOptions).toHaveBeenCalledWith({
      schemas: [],
      validate: false,
    });
    expect(cssDefaults.setOptions).toHaveBeenCalledWith({
      lint: { emptyRules: 'ignore' },
      validate: false,
    });
    expect(scssDefaults.setOptions).toHaveBeenCalledWith({
      lint: { unknownProperties: 'warning' },
      validate: false,
    });
    expect(lessDefaults.setOptions).toHaveBeenCalledWith({
      lint: { zeroUnits: 'ignore' },
      validate: false,
    });
    expect(htmlDefaults.setOptions).toHaveBeenCalledWith({
      format: { wrapLineLength: 120 },
      validate: false,
    });
  });

  it('clears diagnostics markers for existing and newly-created models', async () => {
    const { disableMonacoDiagnostics } = await importFreshModule();
    const existingModel = { uri: 'file:///existing.ts' };
    const newModel = { uri: 'file:///new.ts' };
    const onDidCreateModel = vi.fn();
    const setModelMarkers = vi.fn();

    disableMonacoDiagnostics({
      languages: {},
      editor: {
        getModels: vi.fn(() => [existingModel]),
        onDidCreateModel,
        setModelMarkers,
      },
    });

    expect(setModelMarkers).toHaveBeenCalledWith(existingModel, 'typescript', []);
    expect(setModelMarkers).toHaveBeenCalledWith(existingModel, 'javascript', []);
    expect(setModelMarkers).toHaveBeenCalledWith(existingModel, 'json', []);

    const modelCallback = onDidCreateModel.mock.calls[0][0] as (model: unknown) => void;
    modelCallback(newModel);

    expect(setModelMarkers).toHaveBeenCalledWith(newModel, 'typescript', []);
    expect(setModelMarkers).toHaveBeenCalledWith(newModel, 'javascript', []);
    expect(setModelMarkers).toHaveBeenCalledWith(newModel, 'json', []);
  });

  it('only applies Monaco diagnostics suppression once', async () => {
    const { disableMonacoDiagnostics } = await importFreshModule();
    const typescriptDefaults = createDiagnosticsDefaults({});

    const monaco = {
      languages: {
        typescript: {
          typescriptDefaults,
        },
      },
      editor: {
        getModels: vi.fn(() => []),
        onDidCreateModel: vi.fn(),
        setModelMarkers: vi.fn(),
      },
    };

    disableMonacoDiagnostics(monaco);
    disableMonacoDiagnostics(monaco);

    expect(typescriptDefaults.setDiagnosticsOptions).toHaveBeenCalledTimes(1);
  });
});
