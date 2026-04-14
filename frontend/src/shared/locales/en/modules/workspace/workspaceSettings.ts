const workspaceSettings = {
  header: {
    title: 'Workspace settings',
  },
  empty: {
    title: 'Choose a settings section',
    description: 'Select an option from the menu on the left to begin.',
  },
  basic: {
    header: {
      title: 'Basic settings',
    },
    actions: {
      save: {
        label: 'Save settings',
        saving: 'Saving...',
      },
    },
    status: {
      loading: 'Loading workspace settings...',
    },
    notifications: {
      loadFailed: 'Failed to load workspace settings.',
      saveSuccess: 'Workspace settings updated.',
      saveFailed: 'Failed to save workspace settings.',
    },
    fields: {
      name: {
        label: 'Workspace name',
        placeholder: 'Enter a workspace name',
        helper: 'The workspace name appears in the navigation and header.',
      },
      description: {
        label: 'Workspace description',
        placeholder: 'Describe the workspace',
        helper: 'Explain the workspace purpose to help teammates understand the project.',
      },
      repository: {
        label: 'Git repository',
        placeholder: 'Git repository URL',
        helper: 'The Git repository cannot be changed after the workspace is created.',
      },
      branch: {
        label: 'Branch',
        helper: 'The Git repository branch cannot be changed after the workspace is created.',
      },
      cliType: {
        label: 'CLI type',
        helper: 'This cannot be changed after creation.',
      },
    },
    metadata: {
      title: 'Runtime metadata',
      description: 'Shows the current workspace provisioner, namespace, and overall runtime state.',
      fields: {
        provisioner: 'Provisioner',
        namespace: 'Namespace',
        overallPhase: 'Overall status',
      },
      namespaceFallback: 'Using platform default namespace',
      notAvailable: 'Not available',
      provisioners: {
        docker: 'Docker',
        kubernetes: 'Kubernetes',
      },
      phases: {
        running: 'Running',
        starting: 'Starting',
        reconciling: 'Reconciling',
        pending: 'Pending',
        failed: 'Failed',
        error: 'Error',
        stopped: 'Stopped',
        disabled: 'Disabled',
        unknown: 'Unknown',
      },
    },
    components: {
      title: 'Component status',
      description: 'Shows runtime, browser, and Next.js status with their current URLs.',
      runtime: 'Runtime',
      browser: 'Browser',
      nextjs: 'Next.js',
      fields: {
        internalUrl: 'Internal URL',
        externalUrl: 'External URL',
        lastRestartRequestedAt: 'Last restart request',
      },
    },
  },
  reset: {
    header: {
      title: 'Workspace reset',
    },
    danger: {
      title: 'Danger zone',
      description: 'These actions can permanently affect your workspace. Proceed with caution.',
    },
    lifecycle: {
      title: 'Lifecycle actions',
      description: 'Send restart requests for runtime, browser, Next.js, or the whole workspace.',
      operationState: {
        submitted: 'Submitted',
        processing: 'In progress',
        completed: 'Completed',
        description: 'Current operation state: {{phase}}',
      },
      phases: {
        running: 'Running',
        starting: 'Starting',
        restarting: 'Restarting',
        reconciling: 'Reconciling',
        pending: 'Pending',
        failed: 'Failed',
        error: 'Error',
        stopped: 'Stopped',
        disabled: 'Disabled',
        unknown: 'Unknown',
      },
      actions: {
        runtime: {
          title: 'Restart runtime',
          description: 'Restart the primary execution environment to apply runtime configuration changes.',
          label: 'Restart runtime',
          loading: 'Restarting runtime...',
          successTitle: 'Runtime restart started',
          successDescription: 'The runtime restart request has been submitted.',
          errorTitle: 'Runtime restart failed',
          errorDescription: 'Failed to restart the runtime. Please try again later.',
        },
        browser: {
          title: 'Restart browser',
          description: 'Restart the browser workload when the streamed browser becomes unstable.',
          label: 'Restart browser',
          loading: 'Restarting browser...',
          successTitle: 'Browser restart started',
          successDescription: 'The browser restart request has been submitted.',
          errorTitle: 'Browser restart failed',
          errorDescription: 'Failed to restart the browser. Please try again later.',
        },
        nextjs: {
          title: 'Restart Next.js',
          description: 'Restart the Next.js workload when the preview service becomes unstable.',
          label: 'Restart Next.js',
          loading: 'Restarting Next.js...',
          successTitle: 'Next.js restart started',
          successDescription: 'The Next.js restart request has been submitted.',
          errorTitle: 'Next.js restart failed',
          errorDescription: 'Failed to restart Next.js. Please try again later.',
        },
        workspace: {
          title: 'Restart workspace',
          description: 'Restart the overall workspace execution flow when the whole environment needs recovery.',
          label: 'Restart workspace',
          loading: 'Restarting workspace...',
          successTitle: 'Workspace restart started',
          successDescription: 'The workspace restart request has been submitted.',
          errorTitle: 'Workspace restart failed',
          errorDescription: 'Failed to restart the workspace. Please try again later.',
        },
      },
    },
    delete: {
      title: 'Delete workspace',
      description: 'Permanently delete this workspace and all related data, including configuration files, project files, and history.',
      trigger: 'Delete workspace',
      dialog: {
        title: 'Confirm workspace deletion',
        intro: 'You are about to delete the workspace "{{workspaceName}}".',
        impactTitle: 'This action will permanently remove:',
        impactItems: {
          settings: 'All workspace settings',
          projects: 'Related project files',
          variables: 'Environment variables and configuration',
          history: 'Build and deployment history',
        },
        warning: 'This action cannot be undone.',
        confirmLabel: {
          prefix: 'Type',
          suffix: 'to confirm deletion:',
        },
        cancel: 'Cancel',
        confirm: 'Confirm deletion',
        confirming: 'Deleting...',
      },
      success: {
        title: 'Deletion started',
        description: 'Workspace deletion is running in the background. Redirecting to workspace list...',
      },
      error: {
        title: 'Deletion failed',
        description: 'Failed to delete workspace. Please try again later.',
      },
    },
  },
};

export default workspaceSettings;
