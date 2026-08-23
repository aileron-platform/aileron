import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import {
  adminConsoleStageError,
  adminDisableDiagnosticError,
  bootstrapOidcWorkspaceReadiness,
  buildAdminConsoleUserUrl,
  buildAdminConsoleUrl,
  clickEnabledSwitch,
  enabledSwitchLocator,
  issueExecutionGrant,
  loadOidcDiscovery,
  matchesKeycloakUserUpdate,
  matchesAuthorizationEndpoint,
  persistEnabledSwitch,
  readCanonicalUserSubject,
  requireExpectedKeycloakUserId,
  resolveAdminDisableRecovery,
  safeFailureDiagnostic,
  selectedKeycloakUserId,
  validatesAuthorizationRequest,
  verifyDisabledLoginRejected,
  verifyFreshEnabledSwitchState,
  verifyPlatformAdminAccess,
  waitForAdminConsoleAuthentication,
  waitForAdminConsoleUserSwitch,
  waitForDisableConfirmationAction,
} from './acceptance.mjs';

const oidcWorkspaceOptions = {
  platformUrl: 'https://aileron.example.test',
};

const oidcWorkspaceInput = {
  loginUser: { username: 'manager', password: 'private-password' },
  loginDriver: { kind: 'test-driver' },
};

const readinessResponse = (status, document = {}) => ({
  ok: () => status >= 200 && status < 300,
  json: async () => document,
});

const readinessContext = (id, sessionResponse, events) => {
  const page = { id, url: () => oidcWorkspaceOptions.platformUrl };
  return {
    id,
    page,
    request: {
      get: async () => {
        events.push(`session-${id}`);
        return sessionResponse;
      },
      post: async () => assert.fail('readiness retries must not issue mutations'),
    },
    newPage: async () => {
      events.push(`page-${id}`);
      return page;
    },
    close: async () => events.push(`close-${id}`),
  };
};

test('retries OIDC readiness with fresh contexts and no mutation before a valid session', async () => {
  const events = [];
  const contexts = [
    readinessContext('first', readinessResponse(200), events),
    readinessContext('second', readinessResponse(503), events),
    readinessContext('third', readinessResponse(200, {
      csrf_token: 'current-csrf',
      user: { id: 'current-user', subject: 'current-subject' },
    }), events),
  ];
  const browser = {
    newContext: async () => {
      const context = contexts.shift();
      assert.ok(context, 'readiness retries exceeded supplied contexts');
      events.push(`context-${context.id}`);
      return context;
    },
  };

  const readiness = await bootstrapOidcWorkspaceReadiness(
    browser,
    oidcWorkspaceInput,
    oidcWorkspaceOptions,
    {
      maxAttempts: 3,
      retryDelayMilliseconds: 0,
      sleep: async () => events.push('sleep'),
      loginAction: async (page) => {
        events.push(`login-${page.id}`);
        if (page.id === 'first') throw new Error('private login failure');
      },
    },
  );

  assert.equal(readiness.context.id, 'third');
  assert.equal(readiness.session.user.subject, 'current-subject');
  assert.deepEqual(events, [
    'context-first',
    'page-first',
    'login-first',
    'close-first',
    'sleep',
    'context-second',
    'page-second',
    'login-second',
    'session-second',
    'close-second',
    'sleep',
    'context-third',
    'page-third',
    'login-third',
    'session-third',
  ]);
  await readiness.context.close();
});

test('closes every failed OIDC context and reports secret-safe readiness exhaustion', async () => {
  const events = [];
  const contexts = [
    readinessContext('first', readinessResponse(200, {
      csrf_token: 'private-csrf',
      user: { id: 'private-id', subject: '' },
    }), events),
    readinessContext('second', readinessResponse(401), events),
  ];
  const browser = { newContext: async () => contexts.shift() };

  await assert.rejects(
    bootstrapOidcWorkspaceReadiness(
      browser,
      oidcWorkspaceInput,
      oidcWorkspaceOptions,
      {
        maxAttempts: 2,
        retryDelayMilliseconds: 0,
        sleep: async () => {},
        loginAction: async () => {},
      },
    ),
    (error) => {
      const diagnostic = safeFailureDiagnostic(error);
      assert.deepEqual(diagnostic, {
        code: 'oidc-workspace-readiness-exhausted',
        stage: 'session-readiness',
        attempts: 2,
        errorType: 'Error',
      });
      const serialized = JSON.stringify(diagnostic);
      assert.equal(serialized.includes('aileron.example.test'), false);
      assert.equal(serialized.includes('manager'), false);
      assert.equal(serialized.includes('private'), false);
      return true;
    },
  );
  assert.deepEqual(events.filter((event) => event.startsWith('close-')), [
    'close-first',
    'close-second',
  ]);
});

test('uses the exact configured Keycloak Admin Console host and realm hash', () => {
  assert.equal(
    buildAdminConsoleUrl(
      'https://keycloak.apps.example.test/realms/aileron',
      'https://keycloak-admin.apps.example.test/admin/master/console/',
    ),
    'https://keycloak-admin.apps.example.test/admin/master/console/?kc_locale=en#/aileron/users',
  );
});

test('rejects unsafe Admin Console URLs', () => {
  for (const value of [
    'http://keycloak-admin.apps.example.test/admin/master/console/',
    'https://admin:secret@keycloak-admin.apps.example.test/admin/master/console/',
    'https://keycloak-admin.apps.example.test/admin/master/console/?locale=en',
    ' https://keycloak-admin.apps.example.test/admin/master/console/',
  ]) {
    assert.throws(
      () => buildAdminConsoleUrl(
        'https://keycloak.apps.example.test/realms/aileron',
        value,
      ),
      /exact HTTPS URL/,
    );
  }
});

test('builds a direct Keycloak settings route for an exact canonical user identity', () => {
  const directUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  assert.equal(
    directUrl,
    'https://keycloak-admin.apps.example.test/admin/master/console/?kc_locale=en#/aileron/users/canonical-user-id/settings',
  );
  assert.equal(selectedKeycloakUserId(directUrl), 'canonical-user-id');
});

test('rejects unsafe direct Keycloak user identities and mismatched routes', () => {
  for (const userId of ['', ' user-id', 'user/id', 'user\\id', 'user\nidentity']) {
    assert.throws(
      () => buildAdminConsoleUserUrl(
        'https://keycloak.apps.example.test/realms/aileron',
        'https://keycloak-admin.apps.example.test/admin/master/console/',
        userId,
      ),
      /identity is invalid/,
    );
  }
  assert.equal(selectedKeycloakUserId(
    'https://keycloak-admin.apps.example.test/admin/master/console/#/aileron/users/',
  ), null);
  assert.equal(selectedKeycloakUserId('not-a-url'), null);
});

test('requires the selected Keycloak route identity to exactly match the canonical subject', () => {
  assert.equal(
    requireExpectedKeycloakUserId('canonical-user-id', 'canonical-user-id'),
    'canonical-user-id',
  );
  assert.throws(
    () => requireExpectedKeycloakUserId(null, 'canonical-user-id'),
    /did not expose the selected user identity/,
  );
  assert.throws(
    () => requireExpectedKeycloakUserId('other-user-id', 'canonical-user-id'),
    /unexpected user identity/,
  );
});

test('selects the Keycloak id-suffix enabled switch without matching emailVerified', () => {
  const document = new JSDOM(`
    <input type="checkbox" id="emailVerified-switch" name="emailVerified">
    <input type="checkbox" id="manager-switch">
  `).window.document;
  let matches;
  const strictLocator = {};
  const page = {
    locator: (selector) => {
      matches = [...document.querySelectorAll(selector)];
      return strictLocator;
    },
  };

  const enabledSwitch = enabledSwitchLocator(page);

  assert.equal(enabledSwitch, strictLocator);
  assert.deepEqual(matches.map(({ id }) => id), ['manager-switch']);
});

const evaluateInDom = (element) => async (callback, argument) => {
  const window = element.ownerDocument.defaultView;
  const previousElement = globalThis.HTMLElement;
  const previousInput = globalThis.HTMLInputElement;
  globalThis.HTMLElement = window.HTMLElement;
  globalThis.HTMLInputElement = window.HTMLInputElement;
  try {
    return callback(element, argument);
  } finally {
    globalThis.HTMLElement = previousElement;
    globalThis.HTMLInputElement = previousInput;
  }
};

test('uses one trusted forced Playwright click for the strict checkbox input', async () => {
  const document = new JSDOM(`
    <input type="checkbox" id="manager-switch" checked>
  `).window.document;
  const input = document.querySelector('input');
  const clickArguments = [];
  const enabledSwitch = {
    evaluate: evaluateInDom(input),
    click: async (...args) => clickArguments.push(args),
  };

  await clickEnabledSwitch(enabledSwitch, false);

  assert.equal(input.checked, true);
  assert.deepEqual(clickArguments, [[{ force: true }]]);
});

test('fails closed for invalid checkbox controls before the trusted click', async () => {
  for (const markup of [
    '<input type="checkbox" id="emailVerified-switch" name="emailVerified" checked>',
    '<input type="checkbox" id="manager" checked>',
    '<input type="text" id="manager-switch">',
  ]) {
    const document = new JSDOM(markup).window.document;
    const input = document.querySelector('input');
    const clicks = [];
    const enabledSwitch = {
      evaluate: evaluateInDom(input),
      click: async () => clicks.push('click'),
    };

    await assert.rejects(
      clickEnabledSwitch(enabledSwitch, false),
      (error) => {
        assert.equal(error.name, 'SwitchControlError');
        assert.equal(safeFailureDiagnostic(error).errorType, 'SwitchControlError');
        return true;
      },
    );
    assert.deepEqual(clicks, []);
  }
});

test('classifies an already-set input before attempting interaction', async () => {
  const document = new JSDOM(`
    <input type="checkbox" id="manager-switch">
  `).window.document;
  const input = document.querySelector('input');
  const enabledSwitch = {
    evaluate: evaluateInDom(input),
    click: async () => assert.fail('already-set switch must not be clicked'),
  };

  await assert.rejects(
    clickEnabledSwitch(enabledSwitch, false),
    (error) => {
      assert.equal(error.name, 'SwitchAlreadyStateError');
      assert.equal(safeFailureDiagnostic(error).errorType, 'SwitchAlreadyStateError');
      return true;
    },
  );
});

test('classifies switch inspection and trusted interaction failures', async () => {
  await assert.rejects(
    clickEnabledSwitch({
      evaluate: async () => {
        throw new Error('private inspection detail');
      },
    }, false),
    (error) => error.name === 'SwitchControlError',
  );

  await assert.rejects(
    clickEnabledSwitch({
      evaluate: async () => 'input',
      click: async () => {
        throw new Error('private interaction detail');
      },
    }, false),
    (error) => error.name === 'SwitchInteractionError',
  );
});

test('clicks a legacy button enabled switch without forcing the control', async () => {
  const clicks = [];
  const enabledSwitch = {
    click: async (...args) => clicks.push(args),
    evaluate: async () => 'legacy',
  };

  await clickEnabledSwitch(enabledSwitch, false);

  assert.deepEqual(clicks, [[]]);
});

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const enabledMutationPage = ({
  desiredEnabled,
  receiptMode = 'success',
  confirmClickMode = 'success',
  visibleDialogCount = 1,
  disableButtonCount = 1,
} = {}) => {
  const events = [];
  const receipt = deferred();
  const response = { ok: () => true };
  const confirmButton = {
    click: async (options) => {
      if (options?.trial) {
        events.push('confirm-trial');
        return;
      }
      events.push('confirm');
      if (confirmClickMode === 'failure') throw new Error('private confirmation click detail');
      if (receiptMode === 'timeout') {
        receipt.reject(Object.assign(new Error('private receipt detail'), { name: 'TimeoutError' }));
      } else {
        receipt.resolve(response);
      }
    },
    isEnabled: async () => true,
    isVisible: async () => true,
  };
  const buttons = {
    count: async () => disableButtonCount,
    nth: () => confirmButton,
  };
  const dialog = {
    getByRole: (role, options) => {
      assert.equal(role, 'button');
      assert.equal(options.name.toString(), '/^Disable$/');
      return buttons;
    },
    isVisible: async () => true,
  };
  const dialogs = {
    count: async () => visibleDialogCount,
    nth: () => dialog,
  };
  const page = {
    getByRole: (role, options) => {
      events.push('dialog');
      assert.equal(role, 'dialog');
      assert.equal(options, undefined);
      return dialogs;
    },
    waitForResponse: (predicate) => {
      events.push('arm');
      assert.equal(predicate(keycloakResponse(
        'PUT',
        'https://identity-admin.example.test/admin/realms/aileron/users/user-123',
      )), true);
      assert.equal(predicate(keycloakResponse(
        'PUT',
        'https://identity-admin.example.test/admin/realms/aileron/users/other-user',
      )), false);
      return receipt.promise;
    },
  };
  const enabledSwitch = {
    click: async (...args) => {
      assert.deepEqual(args, [{ force: true }]);
      events.push('switch');
      if (desiredEnabled) {
        if (receiptMode === 'timeout') {
          receipt.reject(Object.assign(new Error('private receipt detail'), {
            name: 'TimeoutError',
          }));
        } else {
          receipt.resolve(response);
        }
      }
    },
    evaluate: async () => 'input',
  };
  return { confirmButton, enabledSwitch, events, page, response };
};

test('disables through one exact dialog action after arming the selected-user PUT', async () => {
  const fixture = enabledMutationPage({ desiredEnabled: false });

  const response = await persistEnabledSwitch(
    fixture.page,
    fixture.enabledSwitch,
    'user-123',
    false,
    { confirmationTimeoutMs: 5 },
  );

  assert.equal(response, fixture.response);
  assert.deepEqual(fixture.events, [
    'switch', 'dialog', 'confirm-trial', 'arm', 'confirm',
  ]);
  assert.equal(fixture.events.filter((event) => event === 'confirm').length, 1);
});

test('enables by arming the selected-user PUT before one trusted switch click', async () => {
  const fixture = enabledMutationPage({ desiredEnabled: true });

  const response = await persistEnabledSwitch(
    fixture.page,
    fixture.enabledSwitch,
    'user-123',
    true,
  );

  assert.equal(response, fixture.response);
  assert.deepEqual(fixture.events, ['arm', 'switch']);
});

test('classifies a missing exact PUT receipt without exposing private details', async () => {
  const fixture = enabledMutationPage({ desiredEnabled: false, receiptMode: 'timeout' });

  await assert.rejects(
    persistEnabledSwitch(
      fixture.page,
      fixture.enabledSwitch,
      'user-123',
      false,
      { confirmationTimeoutMs: 5 },
    ),
    (error) => {
      assert.equal(error.name, 'ExactReceiptError');
      assert.equal(error.adminConsoleStage, 'put-receipt');
      assert.equal(error.message.includes('private'), false);
      assert.equal(safeFailureDiagnostic(error).errorType, 'ExactReceiptError');
      return true;
    },
  );
  assert.deepEqual(fixture.events, [
    'switch', 'dialog', 'confirm-trial', 'arm', 'confirm',
  ]);
});

test('does not confirm when exact-receipt listener setup fails', async () => {
  const fixture = enabledMutationPage({ desiredEnabled: false });
  fixture.page.waitForResponse = () => {
    fixture.events.push('arm');
    throw new Error('private listener detail');
  };

  await assert.rejects(
    persistEnabledSwitch(
      fixture.page,
      fixture.enabledSwitch,
      'user-123',
      false,
      { confirmationTimeoutMs: 5 },
    ),
    (error) => error.name === 'ExactReceiptError' && error.adminConsoleStage === 'put-receipt',
  );
  assert.deepEqual(fixture.events, ['switch', 'dialog', 'confirm-trial', 'arm']);
});

test('classifies the single confirmation click failure after listener arming', async () => {
  const fixture = enabledMutationPage({
    desiredEnabled: false,
    confirmClickMode: 'failure',
  });

  await assert.rejects(
    persistEnabledSwitch(
      fixture.page,
      fixture.enabledSwitch,
      'user-123',
      false,
      { confirmationTimeoutMs: 5 },
    ),
    (error) => (
      error.name === 'DisableConfirmClickError'
      && error.adminConsoleStage === 'disable-confirmation'
      && !error.message.includes('private')
    ),
  );
  assert.deepEqual(fixture.events, [
    'switch', 'dialog', 'confirm-trial', 'arm', 'confirm',
  ]);
});

test('fails closed when multiple visible disable dialogs exist', async () => {
  const fixture = enabledMutationPage({ desiredEnabled: false, visibleDialogCount: 2 });

  await assert.rejects(
    persistEnabledSwitch(
      fixture.page,
      fixture.enabledSwitch,
      'user-123',
      false,
      { confirmationTimeoutMs: 5 },
    ),
    (error) => (
      error.name === 'DisableDialogAmbiguityError'
      && error.adminConsoleStage === 'disable-confirmation'
    ),
  );
  assert.deepEqual(fixture.events, ['switch', 'dialog']);
});

test('fails closed when a visible dialog has multiple exact Disable actions', async () => {
  const fixture = enabledMutationPage({ desiredEnabled: false, disableButtonCount: 2 });

  await assert.rejects(
    persistEnabledSwitch(
      fixture.page,
      fixture.enabledSwitch,
      'user-123',
      false,
      { confirmationTimeoutMs: 5 },
    ),
    (error) => error.name === 'DisableConfirmAmbiguityError',
  );
  assert.deepEqual(fixture.events, ['switch', 'dialog']);
});

test('waits boundedly for the exact Disable action to become actionable', async () => {
  let enabledChecks = 0;
  const delays = [];
  const confirmButton = {
    click: async (options) => assert.equal(options.trial, true),
    isEnabled: async () => {
      enabledChecks += 1;
      return enabledChecks >= 3;
    },
    isVisible: async () => true,
  };
  const dialog = {
    getByRole: (role, options) => {
      assert.equal(role, 'button');
      assert.equal(options.name.toString(), '/^Disable$/');
      return { count: async () => 1, nth: () => confirmButton };
    },
    isVisible: async () => true,
  };
  const page = {
    getByRole: () => ({ count: async () => 1, nth: () => dialog }),
  };

  const action = await waitForDisableConfirmationAction(page, {
    delay: async (delayMs) => delays.push(delayMs),
    intervalMs: 1,
    timeoutMs: 20,
  });

  assert.equal(action, confirmButton);
  assert.equal(enabledChecks, 3);
  assert.deepEqual(delays, [1, 1]);
});

const authenticationPage = ({ state, destinationUrl }) => {
  let currentUrl = state === 'login'
    ? 'https://identity.example.test/realms/master/protocol/openid-connect/auth?state=private'
    : destinationUrl;
  let submitted = false;
  const fills = [];
  const timeout = () => Promise.reject(Object.assign(new Error('private timeout detail'), {
    name: 'TimeoutError',
  }));
  const field = (selector) => ({
    fill: async (value) => fills.push({ selector, value }),
    click: async () => {
      submitted = true;
      currentUrl = destinationUrl;
    },
  });
  const loginForm = {
    first: () => loginForm,
    locator: field,
    waitFor: async ({ state: visibility, timeout: timeoutMs }) => {
      assert.equal(visibility, 'visible');
      assert.equal(timeoutMs, 25);
      if (state !== 'login') return timeout();
    },
  };
  const consoleReady = {
    first: () => consoleReady,
    waitFor: async ({ state: visibility, timeout: timeoutMs }) => {
      assert.equal(visibility, 'visible');
      assert.equal(timeoutMs, 25);
      await Promise.resolve();
      if (state === 'timeout' || (state === 'login' && !submitted)) return timeout();
    },
  };
  return {
    fills,
    wasSubmitted: () => submitted,
    locator: (selector) => (selector.startsWith('form:has(') ? loginForm : consoleReady),
    url: () => currentUrl,
    waitForURL: async (predicate, { timeout: timeoutMs }) => {
      assert.equal(timeoutMs, 25);
      assert.equal(predicate(new URL(destinationUrl)), true);
    },
  };
};

const adminConsoleDestination =
  'https://keycloak-admin.apps.example.test/admin/master/console/?kc_locale=en#/aileron/users';

test('waits for a delayed login redirect and requires authenticated console readiness', async () => {
  const page = authenticationPage({ state: 'login', destinationUrl: adminConsoleDestination });

  await waitForAdminConsoleAuthentication(
    page,
    adminConsoleDestination,
    { username: 'private-admin', password: 'private-password' },
    { timeoutMs: 25 },
  );

  assert.equal(page.wasSubmitted(), true);
  assert.deepEqual(page.fills.map(({ selector }) => selector), [
    'input[name="username"]',
    'input[name="password"]',
  ]);
});

test('accepts an already-authenticated console only after its navigation landmark is visible', async () => {
  const page = authenticationPage({ state: 'console', destinationUrl: adminConsoleDestination });

  await waitForAdminConsoleAuthentication(
    page,
    adminConsoleDestination,
    { username: 'private-admin', password: 'private-password' },
    { timeoutMs: 25 },
  );

  assert.equal(page.wasSubmitted(), false);
  assert.deepEqual(page.fills, []);
});

test('fails closed when neither login nor authenticated console readiness appears', async () => {
  const page = authenticationPage({ state: 'timeout', destinationUrl: adminConsoleDestination });

  await assert.rejects(
    waitForAdminConsoleAuthentication(
      page,
      adminConsoleDestination,
      { username: 'private-admin', password: 'private-password' },
      { timeoutMs: 25 },
    ),
    (error) => {
      assert.equal(error.name, 'TimeoutError');
      assert.equal(error.message.includes('private'), false);
      return true;
    },
  );
});

const readinessPage = ({
  checked = true,
  switchCount = 1,
  visibleOnAttempt = 1,
  routeUserId = 'canonical-user-id',
} = {}) => {
  let attempt = 0;
  let currentUrl = 'about:blank';
  const gotoCalls = [];
  const enabledSwitch = {
    count: async () => switchCount,
    evaluate: async () => checked,
    first: () => enabledSwitch,
    waitFor: async ({ state, timeout }) => {
      assert.equal(state, 'visible');
      assert.equal(timeout, 25);
      if (attempt < visibleOnAttempt) throw Object.assign(new Error('not mounted'), {
        name: 'TimeoutError',
      });
    },
  };
  return {
    gotoCalls,
    goto: async (url, options) => {
      attempt += 1;
      currentUrl = url.replace('canonical-user-id', routeUserId);
      assert.deepEqual(options, { waitUntil: 'domcontentloaded' });
      gotoCalls.push(url);
    },
    url: () => currentUrl,
    locator: () => enabledSwitch,
  };
};

test('retries bounded direct-route readiness before returning the enabled switch', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ visibleOnAttempt: 3 });

  const enabledSwitch = await waitForAdminConsoleUserSwitch(
    page, userUrl, 'canonical-user-id', {
      attempts: 3,
      hydrationSettleMs: 0,
      timeoutMs: 25,
    },
  );

  assert.ok(enabledSwitch);
  assert.deepEqual(page.gotoCalls, [userUrl, userUrl, userUrl]);
});

test('waits for the SPA switch candidate before checking exact uniqueness', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const events = [];
  let currentUrl = 'about:blank';
  let switchVisible = false;
  const firstCandidate = {
    waitFor: async ({ state, timeout }) => {
      assert.equal(state, 'visible');
      assert.equal(timeout, 25);
      events.push('visible');
      switchVisible = true;
    },
  };
  const enabledSwitch = {
    count: async () => {
      events.push('count');
      return switchVisible ? 1 : 0;
    },
    first: () => firstCandidate,
  };
  const page = {
    goto: async (url, options) => {
      currentUrl = url;
      assert.deepEqual(options, { waitUntil: 'domcontentloaded' });
    },
    locator: () => enabledSwitch,
    url: () => currentUrl,
  };

  const result = await waitForAdminConsoleUserSwitch(
    page,
    userUrl,
    'canonical-user-id',
    { attempts: 1, hydrationSettleMs: 0, timeoutMs: 25 },
  );

  assert.equal(result, enabledSwitch);
  assert.deepEqual(events, ['visible', 'count']);
});

test('waits for bounded hydration settle after switch visibility before returning', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage();
  const delays = [];

  const enabledSwitch = await waitForAdminConsoleUserSwitch(
    page,
    userUrl,
    'canonical-user-id',
    {
      attempts: 1,
      hydrationDelay: async (delayMs) => delays.push(delayMs),
      hydrationSettleMs: 3_000,
      timeoutMs: 25,
    },
  );

  assert.ok(enabledSwitch);
  assert.deepEqual(delays, [3_000]);
  assert.deepEqual(page.gotoCalls, [userUrl]);
});

test('fails closed unless the direct user route has exactly one enabled switch', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ switchCount: 2 });

  await assert.rejects(
    waitForAdminConsoleUserSwitch(
      page,
      userUrl,
      'canonical-user-id',
      { attempts: 1, hydrationSettleMs: 0, timeoutMs: 25 },
    ),
    (error) => (
      error.stage === 'switch-readiness'
      && error.errorType === 'SwitchControlError'
    ),
  );
  assert.deepEqual(page.gotoCalls, [userUrl]);
});

test('verifies the receipt before reading state from a fresh exact-route locator', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ checked: false });
  const events = [];
  const goto = page.goto;
  page.goto = async (...args) => {
    events.push('fresh-route');
    return goto(...args);
  };
  const staleEnabledSwitch = {
    evaluate: async () => assert.fail('stale switch must not be read after persistence'),
  };
  const updateResponse = {
    ok: () => {
      events.push('receipt-ok');
      return true;
    },
  };

  const freshEnabledSwitch = await verifyFreshEnabledSwitchState(
    page,
    userUrl,
    'canonical-user-id',
    false,
    updateResponse,
    { readinessOptions: { attempts: 1, hydrationSettleMs: 0, timeoutMs: 25 } },
  );

  assert.notEqual(freshEnabledSwitch, staleEnabledSwitch);
  assert.deepEqual(events, ['receipt-ok', 'fresh-route']);
  assert.deepEqual(page.gotoCalls, [userUrl]);
});

test('fails closed when the fresh exact-route control has the wrong persisted state', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ checked: true });

  await assert.rejects(
    verifyFreshEnabledSwitchState(
      page,
      userUrl,
      'canonical-user-id',
      false,
      { ok: () => true },
      { readinessOptions: { attempts: 1, hydrationSettleMs: 0, timeoutMs: 25 } },
    ),
    /did not persist the requested user state/,
  );
  assert.deepEqual(page.gotoCalls, [userUrl]);
});

test('requires a 2xx receipt before fresh-route verification', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ checked: true });

  await assert.rejects(
    verifyFreshEnabledSwitchState(
      page,
      userUrl,
      'canonical-user-id',
      true,
      { ok: () => false },
      { readinessOptions: { attempts: 1, hydrationSettleMs: 0, timeoutMs: 25 } },
    ),
    /update request failed/,
  );
  assert.deepEqual(page.gotoCalls, []);
});

test('verifies desired true from a fresh exact user route', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ checked: true });

  await verifyFreshEnabledSwitchState(
    page,
    userUrl,
    'canonical-user-id',
    true,
    { ok: () => true },
    { readinessOptions: { attempts: 1, hydrationSettleMs: 0, timeoutMs: 25 } },
  );

  assert.deepEqual(page.gotoCalls, [userUrl]);
});

test('fails closed after bounded switch readiness exhaustion', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ visibleOnAttempt: 4 });

  await assert.rejects(
    waitForAdminConsoleUserSwitch(
      page, userUrl, 'canonical-user-id', { attempts: 3, timeoutMs: 25 },
    ),
    (error) => {
      const diagnostic = safeFailureDiagnostic(adminDisableDiagnosticError(
        'disable-user', null, disabledLoginOptions, error,
      ));
      assert.equal(diagnostic.adminConsoleStage, 'switch-readiness');
      assert.equal(diagnostic.errorType, 'TimeoutError');
      return true;
    },
  );
  assert.deepEqual(page.gotoCalls, [userUrl, userUrl, userUrl]);
});

test('revalidates the canonical route identity before accepting a mounted switch', async () => {
  const userUrl = buildAdminConsoleUserUrl(
    'https://keycloak.apps.example.test/realms/aileron',
    'https://keycloak-admin.apps.example.test/admin/master/console/',
    'canonical-user-id',
  );
  const page = readinessPage({ routeUserId: 'unexpected-user-id' });

  await assert.rejects(
    waitForAdminConsoleUserSwitch(
      page, userUrl, 'canonical-user-id', { attempts: 2, timeoutMs: 25 },
    ),
    (error) => error.stage === 'switch-readiness',
  );
  assert.deepEqual(page.gotoCalls, [userUrl, userUrl]);
});

const keycloakResponse = (method, url) => ({
  request: () => ({ method: () => method }),
  url: () => url,
});

test('matches only the persisted update response for the selected Keycloak user', () => {
  assert.equal(matchesKeycloakUserUpdate(keycloakResponse(
    'PUT',
    'https://identity-admin.example.test/admin/realms/aileron/users/user%2D123',
  ), 'user-123'), true);
  assert.equal(matchesKeycloakUserUpdate(keycloakResponse(
    'GET',
    'https://identity-admin.example.test/admin/realms/aileron/users/user-123',
  ), 'user-123'), false);
  assert.equal(matchesKeycloakUserUpdate(keycloakResponse(
    'PUT',
    'https://identity-admin.example.test/admin/realms/aileron/users/other-user',
  ), 'user-123'), false);
  assert.equal(matchesKeycloakUserUpdate(keycloakResponse(
    'PUT',
    'not-a-url',
  ), 'user-123'), false);
});

test('reports secret-safe admin-console sub-stages without raw failure details', () => {
  const diagnostic = safeFailureDiagnostic(adminDisableDiagnosticError(
    'restore-user',
    null,
    {
      platformUrl: 'https://aileron.example.test',
      issuerUrl: 'https://identity.example.test/realms/aileron',
    },
    adminConsoleStageError(
      'put-receipt',
      Object.assign(new Error('username=secret user-id=sensitive https://private.example'), {
        name: 'TimeoutError',
      }),
    ),
  ));

  assert.deepEqual(diagnostic, {
    code: 'admin-disable-login-probe-failed',
    stage: 'restore-user',
    adminConsoleStage: 'put-receipt',
    currentPath: 'unavailable',
    errorType: 'TimeoutError',
  });
  const serialized = JSON.stringify(diagnostic);
  assert.equal(serialized.includes('username'), false);
  assert.equal(serialized.includes('secret'), false);
  assert.equal(serialized.includes('user-id'), false);
  assert.equal(serialized.includes('sensitive'), false);
  assert.equal(serialized.includes('private.example'), false);
});

const response = (status, document = {}) => ({
  status: () => status,
  json: async () => document,
});

test('reads the canonical Keycloak user identity from the authenticated Manager session', async () => {
  const requested = [];
  const subject = await readCanonicalUserSubject({
    request: {
      get: async (url, options) => {
        requested.push({ url, options });
        return response(200, { user: { subject: 'canonical-user-id' } });
      },
    },
  }, { platformUrl: 'https://aileron.example.test' });

  assert.equal(subject, 'canonical-user-id');
  assert.deepEqual(requested, [{
    url: 'https://aileron.example.test/api/v1/oauth2/session',
    options: {
      headers: {
        Origin: 'https://aileron.example.test',
        Accept: 'application/json',
      },
    },
  }]);
});

test('fails closed when the authenticated Manager session lacks a canonical subject', async () => {
  for (const [status, document] of [
    [401, {}],
    [200, {}],
    [200, { user: { subject: '' } }],
    [200, { user: { subject: ' subject-with-padding ' } }],
  ]) {
    await assert.rejects(
      readCanonicalUserSubject({
        request: { get: async () => response(status, document) },
      }, { platformUrl: 'https://aileron.example.test' }),
      /subject probe failed|subject is invalid/,
    );
  }
});

const diagnosticError = (stage, adminConsoleStage) => adminDisableDiagnosticError(
  stage,
  null,
  disabledLoginOptions,
  adminConsoleStage
    ? adminConsoleStageError(adminConsoleStage, new Error('private failure detail'))
    : new Error('private failure detail'),
);

test('accepts a fresh restored login as authoritative recovery from UI-only uncertainty', () => {
  const result = resolveAdminDisableRecovery({
    uiRestorationError: diagnosticError('restore-user', 'switch'),
  });

  assert.deepEqual(result, {
    restoration: 'verifiedByFreshLogin',
    uiRestorationDiagnostic: {
      code: 'admin-disable-login-probe-failed',
      stage: 'restore-user',
      adminConsoleStage: 'switch',
      currentPath: 'unavailable',
      errorType: 'Error',
    },
  });
});

test('reports ordinary UI restoration when no fallback was needed', () => {
  assert.deepEqual(resolveAdminDisableRecovery({}), {
    restoration: 'reEnabled',
  });
});

test('rethrows an original disable probe error after restoration is separately proven', () => {
  const probeError = diagnosticError('disabled-login-rejection');
  assert.throws(
    () => resolveAdminDisableRecovery({
      probeError,
      uiRestorationError: diagnosticError('restore-user', 'switch'),
      closeError: diagnosticError('admin-console-close', 'context-close'),
    }),
    (error) => error === probeError,
  );
});

test('fails restoration when the fresh restored login fails', () => {
  const restoredLoginError = diagnosticError('restored-login');
  assert.throws(
    () => resolveAdminDisableRecovery({
      probeError: diagnosticError('disabled-login-rejection'),
      uiRestorationError: diagnosticError('restore-user', 'switch'),
      closeError: diagnosticError('admin-console-close', 'context-close'),
      restoredLoginError,
    }),
    (error) => {
      assert.deepEqual(safeFailureDiagnostic(error), {
        code: 'admin-disable-login-probe-failed',
        stage: 'restored-login',
        currentPath: 'unavailable',
        errorType: 'Error',
        uiRestorationStage: 'restore-user',
        uiRestorationAdminConsoleStage: 'switch',
        uiRestorationErrorType: 'Error',
      });
      assert.equal(JSON.stringify(safeFailureDiagnostic(error)).includes('private'), false);
      return true;
    },
  );
});

test('preserves a close failure only after restoration succeeds and no probe failed', () => {
  const closeError = diagnosticError('admin-console-close', 'context-close');
  assert.throws(
    () => resolveAdminDisableRecovery({ closeError }),
    (error) => error === closeError,
  );
});

test('proves platform administrator role, operations, and read-only API access', async () => {
  const requested = [];
  const context = {
    request: {
      get: async (url, options) => {
        requested.push({ url, options });
        if (url.endsWith('/api/v1/oauth2/session')) {
          return response(200, {
            user: {
              id: 'sensitive-user-id',
              subject: 'sensitive-subject',
              username: 'sensitive-username',
              platform_role: 'admin',
              allowed_operations: [
                'marketplace.registry.manage',
                'workspace.create',
                'user_management.manage',
                'marketplace.content.manage',
              ],
            },
            csrf_token: 'sensitive-csrf',
          });
        }
        return response(200);
      },
    },
  };

  const observation = await verifyPlatformAdminAccess(context, {
    platformUrl: 'https://aileron.example.test',
  });

  assert.deepEqual(observation, {
    platformRole: 'admin',
    requiredOperations: 'verified',
    adminUsersStatus: 200,
    marketplaceCatalogStatus: 200,
  });
  assert.deepEqual(requested.map(({ url }) => url), [
    'https://aileron.example.test/api/v1/oauth2/session',
    'https://aileron.example.test/api/v1/admin/users?page=1&pageSize=1',
    'https://aileron.example.test/api/v1/marketplace/packages?page=1&pageSize=1',
  ]);
  assert.equal(JSON.stringify(observation).includes('sensitive'), false);
  assert.ok(requested.every(({ options }) => options.headers.Origin
    === 'https://aileron.example.test'));
});

test('rejects incomplete platform administrator authorization', async () => {
  const context = {
    request: {
      get: async () => response(200, {
        user: {
          platform_role: 'admin',
          allowed_operations: [
            'user_management.manage',
            'marketplace.content.manage',
          ],
        },
      }),
    },
  };

  await assert.rejects(
    verifyPlatformAdminAccess(context, { platformUrl: 'https://aileron.example.test' }),
    /authorization contract is incomplete/,
  );
});

const disabledLoginPage = (url) => ({ url: () => url });

const disabledLoginContext = (status, requested = []) => ({
  request: {
    get: async (url, options) => {
      requested.push({ url, options });
      return response(status);
    },
  },
});

const disabledLoginOptions = {
  platformUrl: 'https://aileron.example.test',
  issuerUrl: 'https://identity.example.test/realms/aileron',
};

test('proves disabled login rejection without relying on Identity error markup', async () => {
  const requested = [];
  const observation = await verifyDisabledLoginRejected(
    disabledLoginPage(
      'https://identity.example.test/realms/aileron/login-actions/authenticate?session=sensitive',
    ),
    disabledLoginContext(401, requested),
    disabledLoginOptions,
  );

  assert.deepEqual(observation, {
    platformReturn: 'blocked',
    managerSessionStatus: 401,
  });
  assert.deepEqual(requested, [{
    url: 'https://aileron.example.test/api/v1/oauth2/session',
    options: {
      headers: {
        Origin: 'https://aileron.example.test',
        Accept: 'application/json',
      },
    },
  }]);
});

test('rejects disabled-login probes that return to Aileron', async () => {
  let sessionRequests = 0;
  const context = disabledLoginContext(401);
  context.request.get = async () => {
    sessionRequests += 1;
    return response(401);
  };

  await assert.rejects(
    verifyDisabledLoginRejected(
      disabledLoginPage('https://aileron.example.test/?state=sensitive'),
      context,
      disabledLoginOptions,
    ),
    (error) => {
      assert.deepEqual(safeFailureDiagnostic(error), {
        code: 'admin-disable-login-probe-failed',
        stage: 'disabled-login-rejection',
        currentPath: 'platform',
        rejectionReason: 'returned-to-platform',
        errorType: 'Error',
      });
      return true;
    },
  );
  assert.equal(sessionRequests, 0);
});

test('requires an explicit unauthenticated Manager session response for disabled login', async () => {
  for (const status of [200, 403, 500]) {
    await assert.rejects(
      verifyDisabledLoginRejected(
        disabledLoginPage(
          'https://identity.example.test/realms/aileron/login-actions/authenticate?state=sensitive',
        ),
        disabledLoginContext(status),
        disabledLoginOptions,
      ),
      (error) => {
        const diagnostic = safeFailureDiagnostic(error);
        assert.deepEqual(diagnostic, {
          code: 'admin-disable-login-probe-failed',
          stage: 'disabled-login-rejection',
          currentPath: 'identity',
          rejectionReason: 'manager-session-not-rejected',
          managerSessionStatus: status,
          errorType: 'Error',
        });
        assert.equal(JSON.stringify(diagnostic).includes('sensitive'), false);
        return true;
      },
    );
  }
});

test('waits for workspace readiness before issuing an execution grant', {
  timeout: 5_000,
}, async () => {
  const options = { platformUrl: 'https://aileron.example.test' };
  const session = { csrf_token: 'csrf-test-token' };
  const availabilitySamples = [
    {
      availability: 'starting',
      runtimeStatus: 'starting',
      runtimeInstanceId: 'runtime-stale',
    },
    {
      availability: 'ready',
      runtimeStatus: 'running',
      runtimeInstanceId: 'runtime-converged',
    },
  ];
  const requests = [];
  const context = {
    request: {
      get: async (url, requestOptions) => {
        const availability = availabilitySamples.shift();
        assert.ok(availability, 'availability polling exceeded the supplied samples');
        requests.push({ method: 'GET', url, requestOptions, availability });
        return {
          ok: () => true,
          json: async () => availability,
        };
      },
      post: async (url, requestOptions) => {
        requests.push({ method: 'POST', url, requestOptions });
        return {
          ok: () => true,
          json: async () => ({ grant: 'test-execution-grant', expiresIn: 60 }),
        };
      },
    },
  };

  const grant = await issueExecutionGrant(
    context,
    options,
    'workspace-123',
    session,
    'workspace-terminal',
    ['terminal'],
  );

  assert.equal(grant, 'test-execution-grant');
  assert.deepEqual(requests.map(({ method }) => method), ['GET', 'GET', 'POST']);
  assert.equal(requests[0].availability.runtimeInstanceId, 'runtime-stale');
  assert.equal(requests[1].availability.runtimeInstanceId, 'runtime-converged');
  assert.deepEqual(requests[2], {
    method: 'POST',
    url: 'https://aileron.example.test/api/v1/workspaces/workspace-123/execution-grants',
    requestOptions: {
      headers: {
        Origin: options.platformUrl,
        'X-CSRF-Token': session.csrf_token,
        Accept: 'application/json',
      },
      data: {
        runtimeInstanceId: 'runtime-converged',
        audience: 'workspace-terminal',
        actions: ['terminal'],
      },
    },
  });
});

test('uses a verified non-Keycloak discovery authorization endpoint', async () => {
  const issuer = 'https://identity.example.test/tenant-a';
  const requested = [];
  const metadata = await loadOidcDiscovery(issuer, async (url) => {
    requested.push(url);
    return {
      ok: true,
      json: async () => ({
        issuer,
        authorization_endpoint: 'https://login.example.net/oauth2/authorize?tenant=tenant-a',
      }),
    };
  });

  assert.deepEqual(requested, [
    'https://identity.example.test/tenant-a/.well-known/openid-configuration',
  ]);
  assert.equal(
    metadata.authorizationEndpoint,
    'https://login.example.net/oauth2/authorize?tenant=tenant-a',
  );
  assert.equal(matchesAuthorizationEndpoint(
    'https://login.example.net/oauth2/authorize?tenant=tenant-a&client_id=aileron',
    metadata.authorizationEndpoint,
  ), true);
  assert.equal(matchesAuthorizationEndpoint(
    'https://identity.example.test/tenant-a/protocol/openid-connect/auth?tenant=tenant-a',
    metadata.authorizationEndpoint,
  ), false);
});

test('retries transient OIDC discovery failures before succeeding', async () => {
  const issuer = 'https://identity.example.test/tenant-a';
  const outcomes = [
    new TypeError('private transport detail'),
    { ok: false },
    {
      ok: true,
      json: async () => ({
        issuer,
        authorization_endpoint: 'https://identity.example.test/oauth2/authorize',
      }),
    },
  ];
  const delays = [];
  const request = async () => {
    const outcome = outcomes.shift();
    if (outcome instanceof Error) throw outcome;
    return outcome;
  };

  const metadata = await loadOidcDiscovery(issuer, request, 100, {
    maxAttempts: 4,
    retryDelayMilliseconds: 7,
    sleep: async (milliseconds) => delays.push(milliseconds),
  });

  assert.equal(metadata.authorizationEndpoint, 'https://identity.example.test/oauth2/authorize');
  assert.deepEqual(delays, [7, 7]);
  assert.equal(outcomes.length, 0);
});

test('bounds transient OIDC discovery retries', async () => {
  let attempts = 0;
  const delays = [];

  await assert.rejects(
    loadOidcDiscovery(
      'https://identity.example.test/tenant-a',
      async () => {
        attempts += 1;
        throw new Error('private transport detail');
      },
      100,
      {
        maxAttempts: 3,
        retryDelayMilliseconds: 11,
        sleep: async (milliseconds) => delays.push(milliseconds),
      },
    ),
    /^Error: OIDC discovery request failed$/,
  );

  assert.equal(attempts, 3);
  assert.deepEqual(delays, [11, 11]);
});

test('does not retry successfully fetched invalid OIDC discovery metadata', async () => {
  let attempts = 0;
  let sleeps = 0;

  await assert.rejects(
    loadOidcDiscovery(
      'https://identity.example.test/tenant-a',
      async () => {
        attempts += 1;
        return {
          ok: true,
          json: async () => ({
            issuer: 'https://identity.example.test/wrong-tenant',
            authorization_endpoint: 'https://identity.example.test/oauth2/authorize',
          }),
        };
      },
      100,
      {
        maxAttempts: 4,
        retryDelayMilliseconds: 1,
        sleep: async () => { sleeps += 1; },
      },
    ),
    /metadata does not match/,
  );

  assert.equal(attempts, 1);
  assert.equal(sleeps, 0);
});

test('requires the complete authorization-code PKCE request contract', () => {
  const options = {
    authorizationEndpoint: 'https://login.example.net/oauth2/authorize?tenant=tenant-a',
    clientId: 'aileron-frontend',
    platformUrl: 'https://aileron.example.test',
  };
  const request = new URL(options.authorizationEndpoint);
  request.searchParams.set('client_id', options.clientId);
  request.searchParams.set('redirect_uri', `${options.platformUrl}/api/v1/oauth2/callback`);
  request.searchParams.set('response_type', 'code');
  request.searchParams.set('scope', 'openid profile email');
  request.searchParams.set('state', 'state-value');
  request.searchParams.set('code_challenge_method', 'S256');
  request.searchParams.set('code_challenge', 'A'.repeat(43));

  assert.equal(validatesAuthorizationRequest(request.toString(), options), true);
  request.searchParams.set('code_challenge', 'constant');
  assert.equal(validatesAuthorizationRequest(request.toString(), options), false);
  request.searchParams.set('code_challenge', 'A'.repeat(43));
  request.searchParams.delete('state');
  assert.equal(validatesAuthorizationRequest(request.toString(), options), false);
});

test('bounds a hanging OIDC discovery request', async () => {
  const hangingRequest = (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error(
      'raw timeout URL?state=sensitive&password=secret',
    )));
  });
  const hangingBody = (_url, options) => Promise.resolve({
    ok: true,
    json: () => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new Error(
        'raw body URL?state=sensitive&password=secret',
      )));
    }),
  });

  for (const request of [hangingRequest, hangingBody]) {
    await assert.rejects(
      loadOidcDiscovery(
        'https://identity.example.test/tenant-a',
        request,
        5,
        {
          maxAttempts: 2,
          retryDelayMilliseconds: 3,
          sleep: async () => {},
        },
      ),
      /timed out/,
    );
  }
});

test('never emits raw exception URLs, state, or passwords', () => {
  const diagnostic = JSON.stringify(safeFailureDiagnostic(new Error(
    'page failed at wss://browser.example/ws?password=secret&state=sensitive',
  )));

  assert.equal(diagnostic.includes('password'), false);
  assert.equal(diagnostic.includes('secret'), false);
  assert.equal(diagnostic.includes('state'), false);
  assert.equal(diagnostic.includes('sensitive'), false);
  assert.deepEqual(JSON.parse(diagnostic), {
    code: 'acceptance-probe-failed',
    stage: 'unclassified',
    currentPath: 'unavailable',
    errorType: 'Error',
  });
});
