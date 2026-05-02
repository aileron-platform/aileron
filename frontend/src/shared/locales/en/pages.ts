const pages = {
  auth: {
    login: {
      title: 'Sign in to Aileron',
      description: 'Sign in with Keycloak SSO.',
      footer: {
        noAccount: "Don't have an account?",
        register: 'Register',
      },
      error: {
        title: 'Sign in failed',
        keycloakFailed: 'Keycloak sign in failed',
      },
      button: {
        signIn: 'Sign in with Keycloak',
        redirecting: 'Redirecting to Keycloak...',
      },
      hint: 'Clicking the button above will redirect you to Keycloak for secure sign in.',
    },
    register: {
      title: 'Register for Aileron',
      description: 'Create a new account with Keycloak.',
      footer: {
        hasAccount: 'Already have an account?',
        login: 'Sign in',
      },
      error: {
        title: 'Registration failed',
        registerFailed: 'Registration failed',
      },
      button: {
        register: 'Register with Keycloak',
        redirecting: 'Redirecting to Keycloak...',
      },
      hint: 'Clicking the button above will redirect you to Keycloak for account registration.',
    },
    callback: {
      loading: {
        label: 'Completing authentication...',
        message: 'Please wait while we verify your identity...',
      },
      error: {
        title: 'Authentication failed',
        invalidCallback: 'Invalid callback: missing code or state parameter',
        authFailed: 'Authentication failed',
        backToLogin: 'Back to Sign In',
        retry: 'Retry',
      },
    },
  },
  profile: {
    title: 'Profile',
    subtitle: 'Manage your personal information and preferences',
    actions: {
      edit: 'Edit profile',
      save: 'Save changes',
      saving: 'Saving...',
    },
    summary: {
      about: 'About me',
    },
    sections: {
      personalInfo: {
        title: 'Personal information',
        description: 'Update your personal information. These details will appear on your profile.',
      },
    },
    fields: {
      username: {
        label: 'Username',
        cannotChange: 'Username cannot be changed',
      },
      firstName: {
        label: 'First Name',
        placeholder: 'Enter your first name',
      },
      lastName: {
        label: 'Last Name',
        placeholder: 'Enter your last name',
      },
      email: {
        label: 'Email',
        placeholder: 'Enter your email address',
        keycloakNote: 'Please update in Keycloak',
      },
    },
    errors: {
      notLoggedIn: 'Please login first',
    },
    status: {
      loading: 'Loading profile...',
    },
    notifications: {
      loadFailed: 'Failed to load profile information.',
      saveFailed: 'Unable to save profile changes.',
    },
  },
  settings: {
    title: 'System settings',
    subtitle: 'Manage application configuration and developer tooling',
    actions: {
      resetDefaults: 'Reset defaults',
      save: 'Save settings',
      saving: 'Saving...',
      saveAll: 'Save all settings',
      syncWorkspace: 'Sync Workspace Settings',
      syncing: 'Syncing...',
    },
    tabs: {
      general: 'General',
      ssh: 'SSH Keys',
      claudeCode: 'Claude Code',
      gemini: 'Gemini',
      opencode: 'OpenCode',
      codex: 'Codex',
      git: 'Git',
    },
    sections: {
      appearance: {
        title: 'Appearance & language',
        description: 'Customize theme, language, and time zone',
        theme: {
          label: 'Theme mode',
          description: 'Choose your preferred interface theme',
          options: {
            light: 'Light mode',
            dark: 'Dark mode',
            system: 'Follow system',
          },
        },
        language: {
          label: 'Language',
          description: 'Select the interface language',
          options: {
            zhTW: 'Traditional Chinese',
            en: 'English',
          },
        },
        timezone: {
          label: 'Time zone',
          description: 'Set the displayed time zone',
          options: {
            utc: 'UTC',
            taipei: 'Taipei (UTC+8)',
            tokyo: 'Tokyo (UTC+9)',
            london: 'London (UTC+0)',
            losAngeles: 'Los Angeles (UTC-8)',
          },
        },
      },
      ssh: {
        title: 'SSH key management',
        description: 'Manage your SSH key pairs',
        privateKey: {
          label: 'Private Key',
          placeholder: '-----BEGIN OPENSSH PRIVATE KEY-----',
          actions: {
            show: 'Show',
            hide: 'Hide',
            copy: 'Copy',
          },
        },
        publicKey: {
          label: 'Public Key',
          placeholder: 'ssh-rsa AAAAB3NzaC1yc2E...',
          copy: 'Copy',
        },
        generate: 'Generate new SSH key pair',
      },
      claudeCode: {
        title: 'Claude Code settings',
        description: 'Configure authentication method and model parameters',
        authMethod: {
          label: 'Authentication Method',
          description: 'Choose Claude authentication method',
          options: {
            subscription: 'Subscription',
            apikey: 'API Key',
          },
        },
        subscription: {
          title: 'Claude Subscription',
          connectButton: 'Authorize Claude',
          disconnectButton: 'Disconnect',
          authCodeLabel: 'Authentication Code',
          authCodePlaceholder: 'ngawlWyaJBpnk0yDb2cPtNzB#jmujzwLN3K-HMpcoiqLiPl06pDbA8f2pBGKbEJ4_U60',
          authCodeHint: 'Authorize Claude in the new window, then paste code below:',
          connectedStatus: '✓ Successfully connected to Claude Subscription',
          expiresAt: 'Expires at',
          status: {
            connected: 'Connected',
            notConnected: 'Not Connected',
          },
          account: 'Account',
          description: 'Your Claude subscription will be used by the Aileron agent to perform your coding tasks.',
          oauthWindow: {
            openingTitle: 'Opening authentication window...',
            openingDescription: 'Complete Claude authentication in the popup window.',
            openedTitle: 'Authentication window opened',
            openedDescription: 'Complete authentication in the new window, then paste the Authentication Code.',
            failedTitle: 'Unable to open authentication window',
            failedDescription: 'Please make sure your browser allows pop-up windows.',
          },
          verifying: 'Verifying authentication code...',
          pleaseWait: 'Please wait',
          saveButton: 'Save',
          cancelButton: 'Cancel',
          success: {
            title: 'Authentication Successful',
            description: 'Successfully connected to Claude Subscription',
            syncDescription: 'Authentication successful! Please click the "Sync Settings" button to sync settings to Workspace.',
          },
          errors: {
            emptyCode: 'Please enter Authentication Code',
            loginRequired: 'You need to log in before starting OAuth authentication',
            authFailed: 'Authentication Failed',
            sessionExpiredTitle: 'Authentication failed',
            sessionExpiredDescription: 'Your login session has expired. Please log in again and retry.',
            unknown: 'Unable to complete authentication',
          },
          disconnect: {
            loginRequiredTitle: 'Unable to disconnect',
            successTitle: 'Disconnected',
            successDescription: 'Authentication data has been cleared',
            failedTitle: 'Failed to disconnect',
            failedDescription: 'Please try again later',
          },
        },
        apikey: {
          title: 'API Key Authentication',
          providerLabel: 'API Provider',
          providerPlaceholder: 'Select API provider',
          providerOptions: {
            anthropic: 'Anthropic',
            awsBedrock: 'AWS Bedrock',
            googleVertexAi: 'Google Vertex AI',
            other: 'Other',
          },
          modelLabel: 'Model',
          modelPlaceholder: 'e.g., claude-sonnet-4-5-20250929 (optional, leave empty to use default)',
          modelHelp: 'If left empty, Claude SDK default model will be used',
        },
        environmentVariables: {
          title: 'Environment Variables',
          description: 'Set API keys and other environment variables',
          addButton: 'Add Variable',
          keyLabel: 'Variable Name',
          valueLabel: 'Variable Value',
          keyPlaceholder: 'e.g., ANTHROPIC_API_KEY',
          valuePlaceholder: 'Variable value',
          emptyState: {
            title: 'No environment variables set',
            description: 'Click "Add Variable" to get started',
          },
          hints: {
            loaded: 'Environment variables are loaded when Claude Code runs',
            required: 'Variable name and value cannot be empty',
            naming: 'Use uppercase letters and underscores for variable names',
          },
        },
        authKey: {
          label: 'Authentication Key',
          placeholder: 'Enter your API key...',
        },
        model: {
          label: 'Model',
          placeholder: 'Select a model',
        },
        provider: {
          label: 'API provider',
          placeholder: 'Select an API provider',
        },
      },
      codex: {
        title: 'Codex settings',
        description: 'Configure ChatGPT subscription login, model, and runtime environment variables for Codex.',
        authMethod: {
          label: 'Authentication method',
          description: 'Select the Codex authentication method',
          options: {
            subscription: 'Subscription',
            apikey: 'API Key',
          },
        },
        login: {
          title: 'ChatGPT subscription',
          account: 'Account',
          notConnectedDescription: 'Sign in to use Codex with your ChatGPT subscription in workspace containers.',
          deviceCode: 'Open the verification page and enter code {{code}}.',
          openVerificationLink: 'Open Codex verification page',
          signInButton: 'Start sign in',
          refreshButton: 'Refresh status',
          cancelButton: 'Cancel',
          logoutButton: 'Logout',
          status: {
            notConnected: 'Not connected',
            pending: 'Pending',
            connected: 'Connected',
            needsRelogin: 'Needs re-login',
            error: 'Error',
          },
          errors: {
            startFailedTitle: 'Unable to start Codex login',
            startFailedDescription: 'Make sure the workspace runtime is running and the Codex login service is available, then try again.',
            logoutFailedTitle: 'Unable to logout Codex',
            logoutFailedDescription: 'Please try again later.',
          },
          window: {
            openedTitle: 'Codex sign-in page opened',
            openedDescription: 'Enter the verification code shown on this screen in the new window.',
            blockedTitle: 'Unable to open sign-in page',
            blockedDescription: 'Open the verification page manually and enter the code shown on this screen.',
          },
        },
        model: {
          label: 'Model',
          placeholder: 'gpt-5.3-codex',
          help: 'This model is passed to Codex runtime settings.',
        },
        environmentVariables: {
          title: 'Codex environment variables',
          description: 'API Key mode writes these variables to workspace runtime containers and applies them to new workspaces.',
        },
      },
      git: {
        title: 'Git settings',
        description: 'Configure Git user information',
        userName: {
          label: 'Git username',
          placeholder: 'Enter your Git username',
        },
        userEmail: {
          label: 'Git email',
          placeholder: 'Enter your Git email',
        },
      },
    },
    notifications: {
      saved: {
        title: 'Settings saved',
        description: 'All settings have been saved successfully',
      },
      loginRequired: {
        title: 'Login required',
        description: 'Please log in first',
      },
      saveLoginRequired: {
        title: 'Unable to save',
        description: 'Please log in first',
      },
      loadFailed: {
        title: 'Failed to load settings',
        description: 'Unable to retrieve your settings from the server.',
      },
      saveFailed: {
        title: 'Failed to save settings',
        description: 'Something went wrong while updating your settings. Please try again later.',
      },
      copied: {
        title: 'Copied',
        description: 'Content copied to clipboard',
      },
      copyFailed: {
        title: 'Copy failed',
        description: 'Unable to copy content to clipboard',
      },
      generateKey: {
        title: 'Generate SSH key',
        progress: 'Generating SSH key pair...',
        successTitle: 'SSH key generated',
        failedTitle: 'Failed to generate SSH key',
        failedDescription: 'Unable to generate SSH key pair',
        description: 'SSH key pair has been successfully generated and saved',
      },
      syncSuccess: {
        title: 'Sync successful',
        description: 'Settings have been successfully synced to {{count}} workspace(s)',
      },
      syncPartial: {
        title: 'Sync partially failed',
        description: 'Some settings failed while syncing to {{count}} workspace(s)',
      },
      syncFailed: {
        title: 'Sync failed',
        description: 'Unable to sync settings to {{count}} workspace(s)',
        loginRequired: 'Please log in first',
      },
      saveAndSyncSuccess: {
        title: 'Save successful',
        description: 'Settings have been saved and synced to workspace',
      },
    },
    status: {
      loading: 'Loading settings...',
    },
  },
};

export default pages;
