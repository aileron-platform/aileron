import labels from './labels';
import navigation from './navigation';
import sidebar from './sidebar';
import layout from './layout';
import claudeCode from './claudeCode';
import codex from './codex';
import fileManagement from './fileManagement';
import versionControl from './versionControl';
import containerManagement from './containerManagement';
import canvas from './canvas';
import browser from './browser';
import automation from './automation';
import workspaceSettings from './workspaceSettings';
import chat from './chat';
import wizard from './wizard';
import agentSettings from './agentSettings';

const workspace = {
  runtime: {
    errors: {
      agenticToolsUnavailable: 'The selected workspace has no supported agentic tools enabled.',
    },
  },
  labels,
  navigation,
  sidebar,
  layout,
  claudeCode,
  codex,
  agentSettings,
  fileManagement,
  versionControl,
  containerManagement,
  canvas,
  browser,
  automation,
  workspaceSettings,
  chat,
  wizard,
};

export default workspace;
