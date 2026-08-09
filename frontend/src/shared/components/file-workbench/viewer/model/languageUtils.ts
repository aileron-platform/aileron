const LANGUAGE_MAP: Record<string, string> = {
  // JavaScript
  js: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  jsx: 'javascript',

  // TypeScript
  ts: 'typescript',
  tsx: 'typescript',

  // Web
  html: 'html',
  htm: 'html',
  css: 'css',
  scss: 'scss',
  sass: 'scss',
  less: 'less',

  // Data formats
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  xml: 'xml',

  // Markdown
  md: 'markdown',
  markdown: 'markdown',

  // Python
  py: 'python',
  pyw: 'python',
  pyi: 'python',

  // Java
  java: 'java',

  // C/C++
  c: 'c',
  h: 'c',
  cpp: 'cpp',
  hpp: 'cpp',
  cc: 'cpp',
  cxx: 'cpp',
  hxx: 'cpp',

  // C#
  cs: 'csharp',
  csx: 'csharp',

  // Go
  go: 'go',

  // Rust
  rs: 'rust',
  rust: 'rust',

  // PHP
  php: 'php',

  // Ruby
  rb: 'ruby',

  // Swift
  swift: 'swift',

  // Kotlin
  kt: 'kotlin',
  kts: 'kotlin',

  // Shell
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  fish: 'shell',

  // PowerShell
  ps1: 'powershell',
  psm1: 'powershell',
  psd1: 'powershell',

  // SQL
  sql: 'sql',

  // R
  r: 'r',

  // Perl
  pl: 'perl',
  pm: 'perl',

  // Lua
  lua: 'lua',

  // Dockerfile
  dockerfile: 'dockerfile',

  // TOML
  toml: 'toml',

  // INI
  ini: 'ini',

  // Properties
  properties: 'properties',

  // GraphQL
  graphql: 'graphql',
  gql: 'graphql',

  // Protocol Buffers
  proto: 'proto',

  // Makefile
  makefile: 'makefile',
  mk: 'makefile',

  // Batch
  bat: 'bat',
  cmd: 'bat',

  // VB
  vb: 'vb',

  // F#
  fs: 'fsharp',
  fsx: 'fsharp',

  // Objective-C
  m: 'objective-c',
  mm: 'objective-c',

  // Scala
  scala: 'scala',

  // Clojure
  clj: 'clojure',
  cljs: 'clojure',

  // Haskell
  hs: 'haskell',

  // Elixir
  ex: 'elixir',
  exs: 'elixir',

  // Dart
  dart: 'dart',
};

export function getLanguageFromFileName(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase();
  if (!ext) return 'plaintext';

  return LANGUAGE_MAP[ext] || 'plaintext';
}
