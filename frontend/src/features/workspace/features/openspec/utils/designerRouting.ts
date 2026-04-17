import type { OpenSpecDesignerSection } from '../../../components/ChatPanel/openSpecApi';

const VALID_SECTIONS: OpenSpecDesignerSection[] = [
  'overview',
  'project-config',
  'schemas',
  'validation',
];

export const getOpenSpecDesignerSection = (pathname: string): OpenSpecDesignerSection => {
  const match = pathname.match(/\/openspec\/designer(?:\/([^/]+))?/);
  const section = match?.[1] as OpenSpecDesignerSection | undefined;
  return VALID_SECTIONS.includes(section ?? 'overview') ? (section ?? 'overview') : 'overview';
};

