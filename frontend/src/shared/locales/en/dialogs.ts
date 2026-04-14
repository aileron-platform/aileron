const dialogs = {
  settingsCheck: {
    title: {
      ready: 'Settings Check Complete',
      incomplete: 'System Settings Required',
    },
    description: {
      ready: 'Your system settings are complete. You can proceed to create a workspace.',
      incomplete: 'Please complete the following required system settings before creating a workspace.',
    },
    requiredSettings: 'Required Settings',
    settings: {
      ssh: 'SSH Keys Settings',
      claudeCode: 'Claude Code Settings',
      git: 'Git Settings',
    },
    warning: 'Please complete {{settings}} settings first',
    allComplete: 'All required settings are complete. You can proceed to create a workspace.',
    actions: {
      goToSettings: 'Go to Settings',
      proceed: 'Proceed',
    },
  },
};

export default dialogs;

