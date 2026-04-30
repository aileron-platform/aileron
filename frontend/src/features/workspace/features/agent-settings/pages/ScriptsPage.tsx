import SkillsPage, { type SkillsPageProps } from './SkillsPage';

const ScriptsPage: React.FC<Omit<SkillsPageProps, 'collectionType'>> = (props) => (
  <SkillsPage {...props} collectionType="scripts" />
);

export default ScriptsPage;
