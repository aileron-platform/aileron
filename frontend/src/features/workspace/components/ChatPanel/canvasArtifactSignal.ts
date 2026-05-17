const CANVAS_ARTIFACT_RE = /<artifact\b(?=[^>]*\btype\s*=\s*["']canvas["'])[^>]*\/?>/i;

export const hasCanvasArtifactSignal = (text: string | null | undefined): boolean => {
  return CANVAS_ARTIFACT_RE.test(text ?? '');
};
