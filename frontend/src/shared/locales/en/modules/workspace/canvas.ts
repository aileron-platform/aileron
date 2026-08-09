const canvas = {
  header: {
    title: 'Canvas',
    actions: {
      fullscreen: {
        enter: 'Enter full screen canvas',
        exit: 'Exit full screen canvas',
      },
    },
    loading: 'Loading Canvas...',
  },
  webCanvas: {
    title: 'Web Canvas',
    routePlaceholder: 'Select or enter a route',
    iframeTitle: 'Workspace Web Canvas',
    loading: 'Loading Canvas...',
    manifest: {
      status: {
        missing: 'No manifest',
        valid: 'Manifest ready',
        invalid: 'Manifest error',
      },
      statusNotice: {
        skill: {
          title: '{{title}}',
          description: 'Active skill canvas from {{skillName}}.',
        },
        user: {
          title: '{{title}}',
          description: 'Active user canvas.',
        },
        details: 'Manifest: {{manifest}} · Runtime: {{runtime}}',
      },
      errors: {
        invalid: {
          title: 'Canvas manifest error',
          description: 'The active canvas manifest is invalid. Fix canvas.json and sync Canvas again.',
        },
      },
      actions: {},
      warnings: {},
    },
    owner: {
      skill: {
        label: 'Skill canvas',
      },
      user: {
        label: 'User canvas',
      },
    },
    default: {
      guidance: {
        title: 'Default Canvas',
        description: 'No active canvas manifest is present. Create /workspace/.aileron/canvas.json to activate one.',
      },
    },
    runtime: {
      healthy: 'Healthy',
      starting: 'Starting',
      errors: {
        startupFailed: 'Startup failed',
      },
    },
    error: {
      title: 'Canvas unavailable',
      defaultMessage: 'Canvas is not ready. Sync or reset the Canvas and try again.',
    },
    actions: {
      missingWorkspace: 'Workspace information is incomplete.',
      unknownError: 'The Canvas action failed.',
      errorTitle: 'Canvas action failed',
      sync: {
        label: 'Sync Canvas',
        successTitle: 'Canvas synced',
        successDescription: 'The Canvas manifest has been reloaded.',
        errorTitle: 'Canvas sync failed',
      },
    },
    review: {
      toolbar: {
        toggle: 'Select Canvas elements to add edit instructions',
      },
      bridgeWaiting: 'Preparing selection mode...',
      form: {
        title: 'Selected target edit instruction',
        placeholder: 'Describe what should change in this element or area.',
        addToList: 'Add to edit list',
        sendNow: 'Send to AI now',
        cancel: 'Cancel',
        close: 'Close edit instruction form',
        dragHandle: 'Move edit instruction form',
      },
      target: {
        area: 'Selected area',
        multi: '{{count}} selected elements',
      },
      status: {
        open: 'Open',
        seen: 'Sent',
        applied: 'Applied',
        dismissed: 'Dismissed',
      },
      notes: {
        title: 'Canvas edit instructions',
        sendToChat: 'Send to AI Chat',
        sendAllToChat: 'Send all to AI Chat',
        delete: 'Delete instruction',
        expand: 'Expand Canvas edit instructions',
        collapse: 'Collapse Canvas edit instructions',
      },
      toast: {
        sentTitle: 'Sent to AI',
        sentDescription: 'The edit instruction was sent through AI Chat.',
        handoffFailedTitle: 'Could not send to AI Chat',
        handoffFailedDescription: 'The edit instruction remains in the list. Try again later.',
      },
      errors: {
        bridge: 'Canvas selection mode could not read this preview.',
        missingTarget: 'Select an element or area first.',
        emptyInstruction: 'Enter an instruction before adding it.',
        createFailed: 'Could not add the edit instruction.',
      },
    },
  },
};

export default canvas;
