const DIAGNOSTIC_MARKER_OWNERS = [
  'typescript',
  'javascript',
  'json',
  'css',
  'scss',
  'less',
  'html',
];

let diagnosticsDisabled = false;

interface MonacoDefaults {
  diagnosticsOptions?: unknown;
  options?: unknown;
  getDiagnosticsOptions?: () => unknown;
  setDiagnosticsOptions?: (options: Record<string, unknown>) => void;
  getOptions?: () => unknown;
  setOptions?: (options: Record<string, unknown>) => void;
}

interface MonacoEditorModel {
  uri?: unknown;
}

interface MonacoAdapter {
  languages?: {
    typescript?: {
      typescriptDefaults?: MonacoDefaults;
      javascriptDefaults?: MonacoDefaults;
    };
    json?: {
      jsonDefaults?: MonacoDefaults;
    };
    css?: {
      cssDefaults?: MonacoDefaults;
      scssDefaults?: MonacoDefaults;
      lessDefaults?: MonacoDefaults;
    };
    html?: {
      htmlDefaults?: MonacoDefaults;
    };
  };
  editor?: {
    getModels?: () => MonacoEditorModel[];
    onDidCreateModel?: (listener: (model: MonacoEditorModel) => void) => unknown;
    setModelMarkers?: (model: MonacoEditorModel, owner: string, markers: unknown[]) => void;
  };
}

const cloneOptions = (options: unknown) => {
  if (!options || typeof options !== 'object') {
    return {};
  }

  return { ...(options as Record<string, unknown>) };
};

const getDiagnosticsOptions = (defaults?: MonacoDefaults) => {
  if (!defaults) {
    return {};
  }

  if (typeof defaults.getDiagnosticsOptions === 'function') {
    return cloneOptions(defaults.getDiagnosticsOptions());
  }

  return cloneOptions(defaults.diagnosticsOptions);
};

const getLanguageOptions = (defaults?: MonacoDefaults) => {
  if (!defaults) {
    return {};
  }

  if (typeof defaults.getOptions === 'function') {
    return cloneOptions(defaults.getOptions());
  }

  return cloneOptions(defaults.options);
};

const setDiagnosticsOptions = (defaults: MonacoDefaults | undefined, nextOptions: Record<string, unknown>) => {
  if (!defaults || typeof defaults.setDiagnosticsOptions !== 'function') {
    return;
  }

  defaults.setDiagnosticsOptions({
    ...getDiagnosticsOptions(defaults),
    ...nextOptions,
  });
};

const setLanguageOptions = (defaults: MonacoDefaults | undefined, nextOptions: Record<string, unknown>) => {
  if (!defaults || typeof defaults.setOptions !== 'function') {
    return;
  }

  defaults.setOptions({
    ...getLanguageOptions(defaults),
    ...nextOptions,
  });
};

const clearDiagnosticsMarkers = (monaco: MonacoAdapter, model: MonacoEditorModel) => {
  if (!monaco?.editor || !model || typeof monaco.editor.setModelMarkers !== 'function') {
    return;
  }

  DIAGNOSTIC_MARKER_OWNERS.forEach((owner) => {
    monaco.editor.setModelMarkers(model, owner, []);
  });
};

export const disableMonacoDiagnostics = (monaco: MonacoAdapter) => {
  if (!monaco?.languages || diagnosticsDisabled) {
    return;
  }

  const { languages } = monaco;

  setDiagnosticsOptions(
    languages.typescript?.typescriptDefaults,
    {
      noSemanticValidation: true,
      noSyntaxValidation: true,
      noSuggestionDiagnostics: true,
    },
  );

  setDiagnosticsOptions(
    languages.typescript?.javascriptDefaults,
    {
      noSemanticValidation: true,
      noSyntaxValidation: true,
      noSuggestionDiagnostics: true,
    },
  );

  setDiagnosticsOptions(languages.json?.jsonDefaults, { validate: false });
  setLanguageOptions(languages.css?.cssDefaults, { validate: false });
  setLanguageOptions(languages.css?.scssDefaults, { validate: false });
  setLanguageOptions(languages.css?.lessDefaults, { validate: false });
  setLanguageOptions(languages.html?.htmlDefaults, { validate: false });

  monaco.editor?.getModels?.().forEach((model) => {
    clearDiagnosticsMarkers(monaco, model);
  });

  monaco.editor?.onDidCreateModel?.((model) => {
    clearDiagnosticsMarkers(monaco, model);
  });

  diagnosticsDisabled = true;
};
