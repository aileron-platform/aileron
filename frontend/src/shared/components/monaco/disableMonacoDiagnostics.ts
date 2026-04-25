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

const cloneOptions = (options: unknown) => {
  if (!options || typeof options !== 'object') {
    return {};
  }

  return { ...(options as Record<string, unknown>) };
};

const getDiagnosticsOptions = (defaults: any) => {
  if (!defaults) {
    return {};
  }

  if (typeof defaults.getDiagnosticsOptions === 'function') {
    return cloneOptions(defaults.getDiagnosticsOptions());
  }

  return cloneOptions(defaults.diagnosticsOptions);
};

const getLanguageOptions = (defaults: any) => {
  if (!defaults) {
    return {};
  }

  if (typeof defaults.getOptions === 'function') {
    return cloneOptions(defaults.getOptions());
  }

  return cloneOptions(defaults.options);
};

const setDiagnosticsOptions = (defaults: any, nextOptions: Record<string, unknown>) => {
  if (!defaults || typeof defaults.setDiagnosticsOptions !== 'function') {
    return;
  }

  defaults.setDiagnosticsOptions({
    ...getDiagnosticsOptions(defaults),
    ...nextOptions,
  });
};

const setLanguageOptions = (defaults: any, nextOptions: Record<string, unknown>) => {
  if (!defaults || typeof defaults.setOptions !== 'function') {
    return;
  }

  defaults.setOptions({
    ...getLanguageOptions(defaults),
    ...nextOptions,
  });
};

const clearDiagnosticsMarkers = (monaco: any, model: any) => {
  if (!monaco?.editor || !model || typeof monaco.editor.setModelMarkers !== 'function') {
    return;
  }

  DIAGNOSTIC_MARKER_OWNERS.forEach((owner) => {
    monaco.editor.setModelMarkers(model, owner, []);
  });
};

export const disableMonacoDiagnostics = (monaco: any) => {
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

  monaco.editor?.getModels?.().forEach((model: any) => {
    clearDiagnosticsMarkers(monaco, model);
  });

  monaco.editor?.onDidCreateModel?.((model: any) => {
    clearDiagnosticsMarkers(monaco, model);
  });

  diagnosticsDisabled = true;
};
