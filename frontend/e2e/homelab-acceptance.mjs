import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const INPUT_PATH = '/run/secrets/acceptance-browser.json';
const SAFE_ERROR_TYPES = new Set([
  'DisableConfirmActionabilityError',
  'DisableConfirmAmbiguityError',
  'DisableConfirmClickError',
  'DisableDialogAmbiguityError',
  'DisableDialogReadinessError',
  'ExactReceiptError',
  'Error',
  'SwitchAlreadyStateError',
  'SwitchControlError',
  'SwitchInteractionError',
  'TimeoutError',
  'TypeError',
]);

class AcceptanceDiagnosticError extends Error {
  constructor(diagnostic) {
    super('acceptance probe failed');
    this.diagnostic = diagnostic;
  }
}

class AdminConsoleStageError extends Error {
  constructor(stage, error) {
    super('admin console operation failed');
    this.stage = stage;
    this.errorType = safeErrorType(error);
  }
}

const safeErrorType = (error) => (
  error instanceof Error && SAFE_ERROR_TYPES.has(error.name)
    ? error.name
    : 'UnknownError'
);

const safePageLocation = (page, options) => {
  if (!page) return 'unavailable';
  try {
    const observed = new URL(page.url());
    if (observed.origin === exactOrigin(options.platformUrl)) return 'platform';
    if (observed.origin === exactOrigin(options.issuerUrl)) return 'identity';
    return 'external';
  } catch {
    return 'invalid-url';
  }
};

export const adminDisableDiagnosticError = (stage, page, options, error) => {
  if (error instanceof AcceptanceDiagnosticError) return error;
  return new AcceptanceDiagnosticError({
    code: 'admin-disable-login-probe-failed',
    stage,
    ...(error instanceof AdminConsoleStageError
      ? { adminConsoleStage: error.stage }
      : {}),
    currentPath: safePageLocation(page, options),
    errorType: error instanceof AdminConsoleStageError
      ? error.errorType
      : safeErrorType(error),
  });
};

export const adminConsoleStageError = (stage, error) => (
  new AdminConsoleStageError(stage, error)
);

export const safeFailureDiagnostic = (error) => {
  if (error instanceof AcceptanceDiagnosticError) return error.diagnostic;
  return {
    code: 'acceptance-probe-failed',
    stage: 'unclassified',
    currentPath: 'unavailable',
    errorType: safeErrorType(error),
  };
};

const option = (name) => {
  const index = process.argv.indexOf(name);
  if (index < 0 || index + 1 >= process.argv.length) {
    throw new Error(`Missing required option: ${name}`);
  }
  return process.argv[index + 1];
};

const requiredUser = (value, name) => {
  if (!value || typeof value.username !== 'string' || typeof value.password !== 'string') {
    throw new Error(`Invalid private browser input: ${name}`);
  }
  return value;
};

const requiredLoginDriver = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid private browser input: loginDriver');
  }
  if (value.kind === 'keycloak' && Object.keys(value).length === 1) {
    return {
      kind: 'keycloak',
      usernameSelector: '#username',
      passwordSelector: '#password',
      submitSelector: '#kc-login',
      errorSelector: '.alert-error, #input-error',
    };
  }
  const selectorKeys = [
    'usernameSelector',
    'passwordSelector',
    'submitSelector',
    'errorSelector',
  ];
  if (
    value.kind !== 'form'
    || Object.keys(value).sort().join(',') !== ['kind', ...selectorKeys].sort().join(',')
    || selectorKeys.some((key) => (
      typeof value[key] !== 'string' || value[key].length < 1 || value[key].length > 256
    ))
  ) {
    throw new Error('Invalid private browser input: loginDriver');
  }
  return value;
};

const exactOrigin = (value) => new URL(value).origin;

const OIDC_DISCOVERY_RETRYABLE = Symbol('oidc-discovery-retryable');

const retryableOidcDiscoveryError = (message) => {
  const error = new Error(message);
  error[OIDC_DISCOVERY_RETRYABLE] = true;
  return error;
};

const defaultSleep = (milliseconds) => new Promise((resolve) => {
  setTimeout(resolve, milliseconds);
});

const OIDC_WORKSPACE_READINESS_ATTEMPTS = 6;
const OIDC_WORKSPACE_READINESS_RETRY_DELAY_MILLISECONDS = 5_000;

export const loadOidcDiscovery = async (
  issuerUrl,
  request = fetch,
  timeoutMilliseconds = 30_000,
  {
    maxAttempts = 4,
    retryDelayMilliseconds = 1_000,
    sleep = defaultSleep,
  } = {},
) => {
  if (
    !Number.isInteger(maxAttempts)
    || maxAttempts < 1
    || !Number.isFinite(retryDelayMilliseconds)
    || retryDelayMilliseconds < 0
    || typeof sleep !== 'function'
  ) {
    throw new Error('Invalid OIDC discovery retry configuration');
  }
  const discoveryUrl = `${issuerUrl.replace(/\/$/, '')}/.well-known/openid-configuration`;
  let metadata;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMilliseconds);
    try {
      let response;
      try {
        response = await request(discoveryUrl, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        });
      } catch {
        throw retryableOidcDiscoveryError(
          controller.signal.aborted
            ? 'OIDC discovery request timed out'
            : 'OIDC discovery request failed',
        );
      }
      if (!response.ok) {
        throw retryableOidcDiscoveryError('OIDC discovery request failed');
      }
      try {
        metadata = await response.json();
      } catch {
        if (controller.signal.aborted) {
          throw retryableOidcDiscoveryError('OIDC discovery request timed out');
        }
        throw new Error('OIDC discovery metadata is invalid');
      }
      break;
    } catch (error) {
      if (!error?.[OIDC_DISCOVERY_RETRYABLE] || attempt === maxAttempts) throw error;
      clearTimeout(timeout);
      await sleep(retryDelayMilliseconds);
    } finally {
      clearTimeout(timeout);
    }
  }
  if (
    !metadata
    || metadata.issuer !== issuerUrl
    || typeof metadata.authorization_endpoint !== 'string'
  ) {
    throw new Error('OIDC discovery metadata does not match the configured issuer');
  }
  const authorizationEndpoint = new URL(metadata.authorization_endpoint);
  if (authorizationEndpoint.protocol !== 'https:') {
    throw new Error('OIDC authorization endpoint must use HTTPS');
  }
  return { authorizationEndpoint: authorizationEndpoint.toString() };
};

export const matchesAuthorizationEndpoint = (observedUrl, expectedUrl) => {
  const observed = new URL(observedUrl);
  const expected = new URL(expectedUrl);
  if (observed.origin !== expected.origin || observed.pathname !== expected.pathname) {
    return false;
  }
  return [...expected.searchParams.entries()].every(
    ([name, value]) => observed.searchParams.getAll(name).includes(value),
  );
};

export const validatesAuthorizationRequest = (observedUrl, options) => {
  if (!matchesAuthorizationEndpoint(observedUrl, options.authorizationEndpoint)) {
    return false;
  }
  const request = new URL(observedUrl);
  const codeChallenge = request.searchParams.get('code_challenge') ?? '';
  const scope = request.searchParams.get('scope')?.split(/\s+/) ?? [];
  return request.searchParams.get('client_id') === options.clientId
    && request.searchParams.get('redirect_uri')
      === `${options.platformUrl}/api/v1/oauth2/callback`
    && request.searchParams.get('response_type') === 'code'
    && scope.includes('openid')
    && Boolean(request.searchParams.get('state'))
    && request.searchParams.get('code_challenge_method') === 'S256'
    && /^[A-Za-z0-9_-]{43,128}$/.test(codeChallenge);
};

const login = async (page, options, user, loginDriver) => {
  let authorizeRequest;
  page.on('request', (request) => {
    if (matchesAuthorizationEndpoint(request.url(), options.authorizationEndpoint)) {
      authorizeRequest = new URL(request.url());
    }
  });
  await page.goto(`${options.platformUrl}/api/v1/oauth2/login?return_path=%2F`, {
    waitUntil: 'domcontentloaded',
  });
  if (!authorizeRequest) throw new Error('OIDC authorization request was not observed');
  if (!validatesAuthorizationRequest(authorizeRequest.toString(), options)) {
    throw new Error('OIDC authorization request does not satisfy the PKCE contract');
  }
  await page.locator(loginDriver.usernameSelector).fill(user.username);
  await page.locator(loginDriver.passwordSelector).fill(user.password);
  await Promise.all([
    page.waitForLoadState('domcontentloaded'),
    page.locator(loginDriver.submitSelector).click(),
  ]);
  return authorizeRequest;
};

const keycloakRealm = (issuerUrl) => {
  const marker = '/realms/';
  const index = issuerUrl.indexOf(marker);
  if (index < 1) throw new Error('Issuer URL is not a realm URL');
  const realm = issuerUrl.slice(index + marker.length).split('/')[0];
  if (!realm) throw new Error('Issuer URL is not a realm URL');
  return realm;
};

export const buildAdminConsoleUrl = (issuerUrl, adminConsoleUrl) => {
  if (
    typeof adminConsoleUrl !== 'string'
    || adminConsoleUrl.length === 0
    || adminConsoleUrl !== adminConsoleUrl.trim()
    || /\s|\\/.test(adminConsoleUrl)
    || [...adminConsoleUrl].some((character) => {
      const code = character.codePointAt(0);
      return code < 32 || code === 127;
    })
  ) {
    throw new Error('Admin Console URL must be an exact HTTPS URL');
  }
  let url;
  try {
    url = new URL(adminConsoleUrl);
  } catch {
    throw new Error('Admin Console URL must be an exact HTTPS URL');
  }
  if (
    url.protocol !== 'https:'
    || !url.hostname
    || url.username
    || url.password
    || url.search
    || url.hash
  ) {
    throw new Error('Admin Console URL must be an exact HTTPS URL');
  }
  url.searchParams.set('kc_locale', 'en');
  url.hash = `/${encodeURIComponent(keycloakRealm(issuerUrl))}/users`;
  return url.toString();
};

export const buildAdminConsoleUserUrl = (issuerUrl, adminConsoleUrl, userId) => {
  if (
    typeof userId !== 'string'
    || userId.length === 0
    || userId !== userId.trim()
    || /[\\/]/.test(userId)
    || [...userId].some((character) => {
      const code = character.codePointAt(0);
      return code < 32 || code === 127;
    })
  ) {
    throw new Error('Keycloak user identity is invalid');
  }
  const url = new URL(buildAdminConsoleUrl(issuerUrl, adminConsoleUrl));
  url.hash = `${url.hash}/${encodeURIComponent(userId)}/settings`;
  return url.toString();
};

export const selectedKeycloakUserId = (url) => {
  try {
    const match = /\/users\/([^/]+)\//.exec(new URL(url).hash);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
};

export const matchesKeycloakUserUpdate = (response, userId) => {
  if (response.request().method() !== 'PUT') return false;
  try {
    const segments = new URL(response.url()).pathname
      .split('/')
      .filter(Boolean)
      .map((segment) => decodeURIComponent(segment));
    return segments.at(-2) === 'users' && segments.at(-1) === userId;
  } catch {
    return false;
  }
};

export const enabledSwitchLocator = (page) => page.locator(
  '#kc-enabled-switch, input[type="checkbox"][name="enabled"], button[role="switch"][aria-label*="Enabled"], input[type="checkbox"][id$="-switch"]:not([id*="emailVerified" i]):not([name="emailVerified" i])',
);

const adminLoginFormLocator = (page) => page.locator(
  'form:has(input[name="username"]):has(input[name="password"]):has(button[type="submit"], input[type="submit"])',
).first();

const adminConsoleReadyLocator = (page) => page.locator(
  '#app nav, #app [role="navigation"]',
).first();

const readEnabledSwitch = async (enabledSwitch) => enabledSwitch.evaluate((element) => (
  element instanceof HTMLInputElement
    ? element.checked
    : element.getAttribute('aria-checked') === 'true'
));

const namedError = (name, message) => Object.assign(new Error(message), { name });

export const clickEnabledSwitch = async (
  enabledSwitch,
  desiredEnabled,
) => {
  let control;
  try {
    control = await enabledSwitch.evaluate((element, desired) => {
      if (element instanceof HTMLInputElement) {
        if (
          element.type !== 'checkbox'
          || !element.id.endsWith('-switch')
          || /emailVerified/i.test(element.id)
          || /emailVerified/i.test(element.name)
        ) return 'invalid';
        return element.checked === desired ? 'already' : 'input';
      }
      return element.tagName.toLowerCase() === 'button' ? 'legacy' : 'invalid';
    }, desiredEnabled);
  } catch {
    throw namedError('SwitchControlError', 'Keycloak Admin Console switch inspection failed');
  }
  if (control === 'invalid') {
    throw namedError('SwitchControlError', 'Keycloak Admin Console enabled switch control is invalid');
  }
  if (control === 'already') {
    throw namedError(
      'SwitchAlreadyStateError',
      'Keycloak Admin Console enabled switch was already in the requested state',
    );
  }
  try {
    if (control === 'input') {
      await enabledSwitch.click({ force: true });
    } else {
      await enabledSwitch.click();
    }
  } catch {
    throw namedError('SwitchInteractionError', 'Keycloak Admin Console switch interaction failed');
  }
};

export const waitForDisableConfirmationAction = async (
  page,
  {
    timeoutMs = 1_000,
    intervalMs = 25,
    delay = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
  } = {},
) => {
  let dialogs;
  try {
    dialogs = page.getByRole('dialog');
  } catch {
    throw namedError(
      'DisableDialogReadinessError',
      'Keycloak Admin Console disable confirmation discovery failed',
    );
  }
  const deadline = Date.now() + timeoutMs;
  do {
    let count;
    try {
      count = await dialogs.count();
    } catch {
      throw namedError(
        'DisableDialogReadinessError',
        'Keycloak Admin Console disable confirmation count failed',
      );
    }
    const visibleDialogs = [];
    for (let index = 0; index < count; index += 1) {
      try {
        const candidate = dialogs.nth(index);
        if (await candidate.isVisible()) visibleDialogs.push(candidate);
      } catch {
        throw namedError(
          'DisableDialogReadinessError',
          'Keycloak Admin Console disable confirmation readiness failed',
        );
      }
    }
    if (visibleDialogs.length > 1) {
      throw namedError(
        'DisableDialogAmbiguityError',
        'Keycloak Admin Console exposed multiple disable confirmations',
      );
    }
    if (visibleDialogs.length === 1) {
      let buttons;
      try {
        buttons = visibleDialogs[0].getByRole('button', { name: /^Disable$/ });
      } catch {
        throw namedError(
          'DisableDialogReadinessError',
          'Keycloak Admin Console disable confirmation action discovery failed',
        );
      }
      let buttonCount;
      try {
        buttonCount = await buttons.count();
      } catch {
        throw namedError(
          'DisableDialogReadinessError',
          'Keycloak Admin Console disable confirmation action count failed',
        );
      }
      const actionable = [];
      for (let index = 0; index < buttonCount; index += 1) {
        try {
          const button = buttons.nth(index);
          if (await button.isVisible() && await button.isEnabled()) actionable.push(button);
        } catch {
          throw namedError(
            'DisableDialogReadinessError',
            'Keycloak Admin Console disable confirmation action readiness failed',
          );
        }
      }
      if (actionable.length > 1) {
        throw namedError(
          'DisableConfirmAmbiguityError',
          'Keycloak Admin Console exposed multiple disable confirmation actions',
        );
      }
      if (actionable.length === 1) {
        try {
          await actionable[0].click({
            trial: true,
            timeout: Math.max(1, deadline - Date.now()),
          });
          return actionable[0];
        } catch (error) {
          if (safeErrorType(error) !== 'TimeoutError') {
            throw namedError(
              'DisableConfirmActionabilityError',
              'Keycloak Admin Console disable confirmation action is not actionable',
            );
          }
        }
      }
    }
    if (Date.now() >= deadline) break;
    try {
      await delay(intervalMs);
    } catch {
      throw namedError(
        'DisableDialogReadinessError',
        'Keycloak Admin Console disable confirmation delay failed',
      );
    }
  } while (Date.now() <= deadline);
  throw namedError(
    'DisableConfirmActionabilityError',
    'Keycloak Admin Console disable confirmation action is unavailable',
  );
};

const exactUserUpdateReceipt = (page, selectedUserId) => {
  let rawPromise;
  try {
    rawPromise = page.waitForResponse(
      (response) => matchesKeycloakUserUpdate(response, selectedUserId),
    );
  } catch {
    throw namedError('ExactReceiptError', 'Keycloak Admin Console update receipt setup failed');
  }
  return Promise.resolve(rawPromise).catch(() => {
    throw namedError('ExactReceiptError', 'Keycloak Admin Console update receipt failed');
  });
};

const stagedPersistError = (stage, error) => {
  if (error instanceof Error) error.adminConsoleStage = stage;
  return error;
};

export const persistEnabledSwitch = async (
  page,
  enabledSwitch,
  selectedUserId,
  desiredEnabled,
  {
    confirmationTimeoutMs = 1_000,
    confirmationPollIntervalMs = 25,
    confirmationDelay,
  } = {},
) => {
  if (desiredEnabled) {
    let updateResponsePromise;
    try {
      updateResponsePromise = exactUserUpdateReceipt(page, selectedUserId);
    } catch (error) {
      throw stagedPersistError('put-receipt', error);
    }
    try {
      await clickEnabledSwitch(enabledSwitch, true);
    } catch (error) {
      throw stagedPersistError('switch-click', error);
    }
    try {
      return await updateResponsePromise;
    } catch (error) {
      throw stagedPersistError('put-receipt', error);
    }
  }

  try {
    await clickEnabledSwitch(enabledSwitch, false);
  } catch (error) {
    throw stagedPersistError('switch-click', error);
  }
  let confirmationButton;
  try {
    confirmationButton = await waitForDisableConfirmationAction(page, {
      timeoutMs: confirmationTimeoutMs,
      intervalMs: confirmationPollIntervalMs,
      ...(confirmationDelay ? { delay: confirmationDelay } : {}),
    });
  } catch (error) {
    throw stagedPersistError('disable-confirmation', error);
  }

  let updateResponsePromise;
  try {
    updateResponsePromise = exactUserUpdateReceipt(page, selectedUserId);
  } catch (error) {
    throw stagedPersistError('put-receipt', error);
  }
  let confirmClickPromise;
  try {
    confirmClickPromise = Promise.resolve(confirmationButton.click()).catch(() => {
      throw namedError(
        'DisableConfirmClickError',
        'Keycloak Admin Console disable confirmation action failed',
      );
    });
  } catch {
    throw stagedPersistError('disable-confirmation', namedError(
      'DisableConfirmClickError',
      'Keycloak Admin Console disable confirmation action failed',
    ));
  }
  try {
    const [updateResponse] = await Promise.all([updateResponsePromise, confirmClickPromise]);
    return updateResponse;
  } catch (error) {
    const stage = error?.name === 'DisableConfirmClickError'
      ? 'disable-confirmation'
      : 'put-receipt';
    throw stagedPersistError(stage, error);
  }
};

const timeoutError = (message) => Object.assign(new Error(message), { name: 'TimeoutError' });

const waitForFirstVisible = async (candidates, timeoutMs) => {
  try {
    return await Promise.any(candidates.map(async ([name, locator]) => {
      await locator.waitFor({ state: 'visible', timeout: timeoutMs });
      return name;
    }));
  } catch {
    throw timeoutError('Keycloak Admin Console authentication readiness timed out');
  }
};

export const waitForAdminConsoleAuthentication = async (
  page,
  adminConsoleUrl,
  admin,
  { timeoutMs = 30_000 } = {},
) => {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error('Admin Console authentication timeout must be positive');
  }
  const expectedUrl = new URL(adminConsoleUrl);
  const loginForm = adminLoginFormLocator(page);
  const consoleReady = adminConsoleReadyLocator(page);
  const state = await waitForFirstVisible([
    ['login', loginForm],
    ['console', consoleReady],
  ], timeoutMs);

  if (state === 'login') {
    await loginForm.locator('input[name="username"]').fill(admin.username);
    await loginForm.locator('input[name="password"]').fill(admin.password);
    await Promise.all([
      page.waitForURL((url) => (
        url.origin === expectedUrl.origin && url.pathname === expectedUrl.pathname
      ), { timeout: timeoutMs }),
      consoleReady.waitFor({ state: 'visible', timeout: timeoutMs }),
      loginForm.locator('button[type="submit"], input[type="submit"]').click(),
    ]);
  }

  const observedUrl = new URL(page.url());
  if (
    observedUrl.origin !== expectedUrl.origin
    || observedUrl.pathname !== expectedUrl.pathname
  ) {
    throw new Error('Keycloak Admin Console authentication did not reach the configured console');
  }
};

export const waitForAdminConsoleUserSwitch = async (
  page,
  userUrl,
  expectedUserId,
  {
    attempts = 3,
    timeoutMs = 5_000,
    hydrationSettleMs = 3_000,
    hydrationDelay = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
  } = {},
) => {
  if (!Number.isInteger(attempts) || attempts < 1) {
    throw new Error('Admin Console readiness attempts must be a positive integer');
  }
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error('Admin Console readiness timeout must be positive');
  }
  if (!Number.isFinite(hydrationSettleMs) || hydrationSettleMs < 0) {
    throw new Error('Admin Console hydration settle must be non-negative');
  }
  if (typeof hydrationDelay !== 'function') {
    throw new Error('Admin Console hydration delay must be callable');
  }
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      await page.goto(userUrl, { waitUntil: 'domcontentloaded' });
      requireExpectedKeycloakUserId(selectedKeycloakUserId(page.url()), expectedUserId);
      const enabledSwitch = enabledSwitchLocator(page);
      await enabledSwitch.first().waitFor({ state: 'visible', timeout: timeoutMs });
      if (await enabledSwitch.count() !== 1) {
        throw namedError(
          'SwitchControlError',
          'Keycloak Admin Console enabled switch is not unique',
        );
      }
      requireExpectedKeycloakUserId(selectedKeycloakUserId(page.url()), expectedUserId);
      await hydrationDelay(hydrationSettleMs);
      requireExpectedKeycloakUserId(selectedKeycloakUserId(page.url()), expectedUserId);
      return enabledSwitch;
    } catch (error) {
      lastError = error;
    }
  }
  throw adminConsoleStageError('switch-readiness', lastError);
};

export const verifyFreshEnabledSwitchState = async (
  page,
  userUrl,
  selectedUserId,
  desiredEnabled,
  updateResponse,
  { readinessOptions } = {},
) => {
  if (!updateResponse.ok()) {
    throw new Error('Keycloak Admin Console user update request failed');
  }
  const freshEnabledSwitch = await waitForAdminConsoleUserSwitch(
    page, userUrl, selectedUserId, readinessOptions,
  );
  const finalEnabled = await readEnabledSwitch(freshEnabledSwitch);
  if (finalEnabled !== desiredEnabled) {
    throw new Error('Keycloak Admin Console did not persist the requested user state');
  }
  return freshEnabledSwitch;
};

export const requireExpectedKeycloakUserId = (selectedUserId, expectedUserId) => {
  if (!selectedUserId) {
    throw new Error('Keycloak Admin Console did not expose the selected user identity');
  }
  if (selectedUserId !== expectedUserId) {
    throw new Error('Keycloak Admin Console selected an unexpected user identity');
  }
  return selectedUserId;
};

const openAdminConsoleUser = async (browser, options, admin, expectedUserId) => {
  const context = await browser.newContext({ locale: 'en-US' });
  let stage = 'navigation';
  try {
    const page = await context.newPage();
    const configuredAdminUrl = new URL(options.adminConsoleUrl);
    await page.goto(buildAdminConsoleUrl(
      options.issuerUrl,
      options.adminConsoleUrl,
    ), {
      waitUntil: 'domcontentloaded',
    });
    stage = 'login';
    await waitForAdminConsoleAuthentication(page, configuredAdminUrl, admin);
    const consoleLocale = await page.evaluate(() => document.documentElement.lang);
    if (!consoleLocale.toLowerCase().startsWith('en')) {
      throw new Error('Keycloak Admin Console did not activate the required English locale');
    }
    stage = 'user-selection';
    await page.goto(buildAdminConsoleUserUrl(
      options.issuerUrl,
      options.adminConsoleUrl,
      expectedUserId,
    ), { waitUntil: 'domcontentloaded' });
    await page.waitForURL(/\/users\/[^/]+\//);
    const selectedUserId = requireExpectedKeycloakUserId(
      selectedKeycloakUserId(page.url()),
      expectedUserId,
    );
    return { context, page, selectedUserId };
  } catch (error) {
    try {
      await context.close();
    } catch {
      // Preserve the actionable open/select stage.
    }
    throw adminConsoleStageError(stage, error);
  }
};

const setOpenAdminConsoleUserEnabled = async (
  page, selectedUserId, desiredEnabled, userUrl,
) => {
  let stage = 'user-selection';
  try {
    const enabledSwitch = await waitForAdminConsoleUserSwitch(
      page, userUrl, selectedUserId,
    );
    stage = 'switch';
    const enabled = await readEnabledSwitch(enabledSwitch);
    if (enabled !== desiredEnabled) {
      stage = 'put-receipt';
      const updateResponse = await persistEnabledSwitch(
        page, enabledSwitch, selectedUserId, desiredEnabled,
      );
      stage = 'local-state';
      await verifyFreshEnabledSwitchState(
        page, userUrl, selectedUserId, desiredEnabled, updateResponse,
      );
      return selectedUserId;
    }
    stage = 'local-state';
    const finalEnabled = await readEnabledSwitch(enabledSwitch);
    if (finalEnabled !== desiredEnabled) {
      throw new Error('Keycloak Admin Console did not persist the requested user state');
    }
    return selectedUserId;
  } catch (error) {
    if (error instanceof AdminConsoleStageError) throw error;
    throw adminConsoleStageError(error?.adminConsoleStage ?? stage, error);
  }
};

export const bootstrapOidcWorkspaceReadiness = async (
  browser,
  input,
  options,
  {
    maxAttempts = OIDC_WORKSPACE_READINESS_ATTEMPTS,
    retryDelayMilliseconds = OIDC_WORKSPACE_READINESS_RETRY_DELAY_MILLISECONDS,
    sleep = defaultSleep,
    loginAction = login,
  } = {},
) => {
  if (
    !Number.isInteger(maxAttempts)
    || maxAttempts < 1
    || !Number.isFinite(retryDelayMilliseconds)
    || retryDelayMilliseconds < 0
    || typeof sleep !== 'function'
    || typeof loginAction !== 'function'
  ) {
    throw new Error('Invalid OIDC Workspace readiness retry configuration');
  }
  const loginUser = requiredUser(input.loginUser, 'loginUser');
  let lastError;
  let lastStage = 'login-readiness';
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let context;
    try {
      context = await browser.newContext();
      const page = await context.newPage();
      await loginAction(page, options, loginUser, input.loginDriver);
      if (exactOrigin(page.url()) !== exactOrigin(options.platformUrl)) {
        throw new Error('OIDC login did not return to Aileron');
      }
      lastStage = 'session-readiness';
      const sessionResponse = await context.request.get(
        `${options.platformUrl}/api/v1/oauth2/session`,
        { headers: { Origin: options.platformUrl, Accept: 'application/json' } },
      );
      if (!sessionResponse.ok()) {
        throw new Error('Authenticated Manager session bootstrap failed');
      }
      const session = await sessionResponse.json();
      if (
        typeof session.csrf_token !== 'string'
        || session.csrf_token.length === 0
        || session.csrf_token !== session.csrf_token.trim()
        || typeof session.user?.id !== 'string'
        || session.user.id.length === 0
        || session.user.id !== session.user.id.trim()
        || typeof session.user.subject !== 'string'
        || session.user.subject.length === 0
        || session.user.subject !== session.user.subject.trim()
      ) {
        throw new Error('Authenticated Manager session did not expose identity and CSRF evidence');
      }
      return { context, loginUser, session };
    } catch (error) {
      lastError = error;
      if (context) {
        try {
          await context.close();
        } catch (closeError) {
          lastError = closeError;
        }
      }
      if (attempt < maxAttempts) {
        await sleep(retryDelayMilliseconds);
        lastStage = 'login-readiness';
      }
    }
  }
  throw new AcceptanceDiagnosticError({
    code: 'oidc-workspace-readiness-exhausted',
    stage: lastStage,
    attempts: maxAttempts,
    errorType: safeErrorType(lastError),
  });
};

const runOidcWorkspace = async (browser, input, options) => {
  const { context, loginUser, session } = await bootstrapOidcWorkspaceReadiness(
    browser,
    input,
    options,
  );
  const authenticatedHeaders = {
    Origin: options.platformUrl,
    'X-CSRF-Token': session.csrf_token,
  };
  try {
    const response = await context.request.post(`${options.platformUrl}/api/v1/workspaces`, {
      headers: authenticatedHeaders,
      data: {
        name: `acceptance-${options.runId}`,
        description: 'HomeLab acceptance workspace',
        runtime: 'universal',
        agenticTools: ['codex'],
      },
    });
    if (response.status() !== 201) throw new Error('Authenticated Workspace creation failed');
    const workspace = await response.json();
    const detailResponse = await context.request.get(
      `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspace.id)}`,
      { headers: authenticatedHeaders },
    );
    if (!detailResponse.ok()) throw new Error('Created Workspace is not readable');
    const detail = await detailResponse.json();
    if (
      detail.id !== workspace.id
      || detail.owner?.id !== session.user.id
      || detail.owner?.username !== loginUser.username
    ) {
      throw new Error('Created Workspace is not owned by the authenticated Manager user');
    }
    return {
      flow: 'authorization-code-pkce',
      createdWorkspaceId: workspace.id,
      userSubject: session.user.subject,
    };
  } finally {
    await context.close();
  }
};

const bootstrapSession = async (context, options) => {
  const response = await context.request.get(
    `${options.platformUrl}/api/v1/oauth2/session`,
    { headers: { Origin: options.platformUrl, Accept: 'application/json' } },
  );
  if (!response.ok()) throw new Error('Authenticated Manager session bootstrap failed');
  const session = await response.json();
  if (
    typeof session.csrf_token !== 'string'
    || session.csrf_token.length === 0
    || typeof session.user?.id !== 'string'
    || session.user.id.length === 0
  ) {
    throw new Error('Authenticated Manager session did not expose CSRF evidence');
  }
  return session;
};

const workspaceHeaders = (options, session, mutation = false) => ({
  Origin: options.platformUrl,
  Accept: 'application/json',
  ...(mutation ? { 'X-CSRF-Token': session.csrf_token } : {}),
});

const readWorkspaceDetail = async (context, options, workspaceId, session) => {
  const response = await context.request.get(
    `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspaceId)}`,
    { headers: workspaceHeaders(options, session) },
  );
  if (!response.ok()) throw new Error('Workspace lifecycle detail probe failed');
  return await response.json();
};

const readWorkspaceAvailability = async (context, options, workspaceId, session) => {
  const response = await context.request.get(
    `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspaceId)}/availability`,
    { headers: workspaceHeaders(options, session) },
  );
  if (!response.ok()) throw new Error('Workspace lifecycle availability probe failed');
  return await response.json();
};

const waitForWorkspaceState = async (description, readState, accepted) => {
  const deadline = Date.now() + 600_000;
  while (Date.now() <= deadline) {
    const state = await readState();
    if (accepted(state)) return state;
    await new Promise((resolve) => setTimeout(resolve, 2_000));
  }
  throw new Error(`${description} did not converge`);
};

const waitForWorkspaceReady = async (context, options, workspaceId, session) => (
  await waitForWorkspaceState(
    'Workspace Ready state',
    () => readWorkspaceAvailability(context, options, workspaceId, session),
    (availability) => (
      availability.availability === 'ready'
      && availability.runtimeStatus === 'running'
      && typeof availability.runtimeInstanceId === 'string'
      && availability.runtimeInstanceId.length > 0
    ),
  )
);

const runWorkspaceLifecycle = async (browser, input, options) => {
  const loginUser = requiredUser(input.loginUser, 'loginUser');
  if (!options.workspaceId) throw new Error('Workspace identity is required for lifecycle acceptance');
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await login(page, options, loginUser, input.loginDriver);
    if (exactOrigin(page.url()) !== exactOrigin(options.platformUrl)) {
      throw new Error('OIDC login did not return to Aileron');
    }
    const session = await bootstrapSession(context, options);
    const workspaceId = options.workspaceId;
    await waitForWorkspaceReady(context, options, workspaceId, session);

    for (const component of ['runtime', 'browser', 'canvas']) {
      const response = await context.request.post(
        `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspaceId)}/components/${component}/restart`,
        { headers: workspaceHeaders(options, session, true) },
      );
      if (response.status() !== 202) {
        throw new Error(`Workspace ${component} restart request failed`);
      }
      const command = await response.json();
      if (
        command.workspaceId !== workspaceId
        || command.component !== component
        || typeof command.jobId !== 'string'
        || command.jobId.length === 0
        || !Number.isInteger(command.targetRevision)
        || command.targetRevision < 1
      ) {
        throw new Error(`Workspace ${component} restart response is invalid`);
      }
      await waitForWorkspaceState(
        `Workspace ${component} restart`,
        () => readWorkspaceDetail(context, options, workspaceId, session),
        (detail) => {
          const status = detail.components?.[component];
          return status?.desiredRevision === command.targetRevision
            && status?.observedRevision === command.targetRevision
            && status?.phase === 'Running'
            && status?.ready === true;
        },
      );
      await waitForWorkspaceReady(context, options, workspaceId, session);
    }

    const stopResponse = await context.request.post(
      `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspaceId)}/stop`,
      { headers: workspaceHeaders(options, session, true) },
    );
    if (stopResponse.status() !== 202) throw new Error('Workspace stop request failed');
    const stopCommand = await stopResponse.json();
    if (
      stopCommand.workspaceId !== workspaceId
      || typeof stopCommand.jobId !== 'string'
      || stopCommand.jobId.length === 0
    ) {
      throw new Error('Workspace stop response is invalid');
    }
    await waitForWorkspaceState(
      'Workspace Stopped state',
      () => readWorkspaceAvailability(context, options, workspaceId, session),
      (availability) => (
        availability.availability === 'stopped'
        && availability.runtimeStatus === 'stopped'
        && availability.runtimeInstanceId === null
      ),
    );

    const startResponse = await context.request.post(
      `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspaceId)}/start`,
      { headers: workspaceHeaders(options, session, true) },
    );
    if (startResponse.status() !== 202) throw new Error('Workspace start request failed');
    const startCommand = await startResponse.json();
    if (
      startCommand.workspaceId !== workspaceId
      || typeof startCommand.jobId !== 'string'
      || startCommand.jobId.length === 0
    ) {
      throw new Error('Workspace start response is invalid');
    }
    await waitForWorkspaceReady(context, options, workspaceId, session);
    const finalDetail = await readWorkspaceDetail(context, options, workspaceId, session);
    if (!['runtime', 'browser', 'canvas'].every((component) => (
      finalDetail.components?.[component]?.phase === 'Running'
      && finalDetail.components?.[component]?.ready === true
    ))) {
      throw new Error('Workspace components are not Ready after start');
    }
    return {
      componentsRestarted: ['runtime', 'browser', 'canvas'],
      stopObserved: 'stopped',
      startObserved: 'ready',
    };
  } finally {
    await context.close();
  }
};

const runBrowserSession = async (browser, input, options) => {
  const loginUser = requiredUser(input.loginUser, 'loginUser');
  if (!options.workspaceId) throw new Error('Workspace identity is required for Browser UI acceptance');
  const context = await browser.newContext();
  const page = await context.newPage();
  let stage = 'oidc-login';
  const consoleCounts = {};
  const failedRequestPaths = [];
  page.on('console', (message) => {
    consoleCounts[message.type()] = (consoleCounts[message.type()] ?? 0) + 1;
  });
  page.on('requestfailed', (request) => {
    try {
      const url = new URL(request.url());
      const errorText = request.failure()?.errorText ?? '';
      failedRequestPaths.push({
        method: request.method(),
        path: url.pathname,
        failure: /^net::[A-Z0-9_]+$/.test(errorText) ? errorText : 'unknown',
      });
    } catch {
      failedRequestPaths.push({ method: request.method(), path: 'invalid-url', failure: 'unknown' });
    }
  });
  try {
    await login(page, options, loginUser, input.loginDriver);
    if (exactOrigin(page.url()) !== exactOrigin(options.platformUrl)) {
      throw new Error('OIDC login did not return to Aileron');
    }
    stage = 'workspace-readiness';
    const session = await bootstrapSession(context, options);
    await waitForWorkspaceReady(context, options, options.workspaceId, session);
    const route = `/workspaces/${encodeURIComponent(options.workspaceId)}/browser`;
    stage = 'browser-route';
    await page.goto(`${options.platformUrl}${route}`, { waitUntil: 'domcontentloaded' });
    const readiness = page.getByTestId('browser-session-readiness');
    await readiness.waitFor({ state: 'visible', timeout: 120_000 });
    stage = 'transport-readiness';
    await page.waitForFunction(() => {
      const element = document.querySelector('[data-testid="browser-session-readiness"]');
      if (!(element instanceof HTMLElement)) return false;
      return element.dataset.connectionState === 'connected'
        && element.dataset.websocketConnected === 'true'
        && element.dataset.webrtcConnected === 'true'
        && element.dataset.dataChannelOpen === 'true'
        && element.dataset.liveVideoTrack === 'true';
    }, undefined, { timeout: 120_000 });
    const video = page.getByTestId('browser-video');
    await video.waitFor({ state: 'visible' });
    stage = 'live-video';
    await page.waitForFunction(() => {
      const element = document.querySelector('[data-testid="browser-video"]');
      if (!(element instanceof HTMLVideoElement)) return false;
      const stream = element.srcObject;
      return stream instanceof MediaStream
        && stream.getVideoTracks().some((track) => track.readyState === 'live')
        && element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA
        && element.videoWidth > 0
        && element.videoHeight > 0;
    }, undefined, { timeout: 120_000 });
    const dimensions = await video.evaluate((element) => ({
      videoWidth: element.videoWidth,
      videoHeight: element.videoHeight,
    }));
    return {
      route,
      websocket: 'open',
      webrtc: 'connected',
      videoTrack: 'live',
      dataChannel: 'open',
      ...dimensions,
    };
  } catch (error) {
    const readiness = await page.getByTestId('browser-session-readiness').evaluate((element) => ({
      connectionState: element.dataset.connectionState ?? 'missing',
      websocketConnected: element.dataset.websocketConnected ?? 'missing',
      webrtcConnected: element.dataset.webrtcConnected ?? 'missing',
      dataChannelOpen: element.dataset.dataChannelOpen ?? 'missing',
      liveVideoTrack: element.dataset.liveVideoTrack ?? 'missing',
    })).catch(() => null);
    let currentPath = 'invalid-url';
    try {
      currentPath = new URL(page.url()).pathname;
    } catch {
      currentPath = 'invalid-url';
    }
    throw new AcceptanceDiagnosticError({
      code: 'browser-session-probe-failed',
      stage,
      currentPath,
      readiness,
      consoleCounts,
      failedRequestPaths: failedRequestPaths.slice(-20),
      errorType: safeErrorType(error),
    });
  } finally {
    await context.close();
  }
};

export const issueExecutionGrant = async (
  context,
  options,
  workspaceId,
  session,
  audience,
  actions,
) => {
  const availability = await waitForWorkspaceReady(context, options, workspaceId, session);
  const response = await context.request.post(
    `${options.platformUrl}/api/v1/workspaces/${encodeURIComponent(workspaceId)}/execution-grants`,
    {
      headers: {
        Origin: options.platformUrl,
        'X-CSRF-Token': session.csrf_token,
        Accept: 'application/json',
      },
      data: {
        runtimeInstanceId: availability.runtimeInstanceId,
        audience,
        actions,
      },
    },
  );
  if (!response.ok()) throw new Error('Workspace execution grant request failed');
  const grant = await response.json();
  if (typeof grant.grant !== 'string' || grant.grant.length === 0 || grant.expiresIn !== 60) {
    throw new Error('Workspace execution grant response is invalid');
  }
  return grant.grant;
};

const runTerminalWebSocket = async (page, options, workspaceId, grant, mode) => page.evaluate(
  async ({ platformUrl, workspaceId: id, grant: executionGrant, probeMode }) => {
    const encodeGrant = (value) => {
      const bytes = new TextEncoder().encode(value);
      let binary = '';
      for (const byte of bytes) binary += String.fromCharCode(byte);
      return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
    };
    const socketUrl = new URL(
      `/workspaces/${id}/runtime/ws/terminal?workspace_id=${encodeURIComponent(id)}`,
      platformUrl,
    );
    socketUrl.protocol = socketUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = `aileron-acceptance-${crypto.randomUUID()}`;
    const messages = [];
    return await new Promise((resolve, reject) => {
      const socket = new WebSocket(socketUrl.toString(), [
        'aileron-terminal-v1',
        `bearer.${encodeGrant(executionGrant)}`,
      ]);
      let tabId = null;
      let settled = false;
      const timeout = setTimeout(() => {
        if (!settled) {
          settled = true;
          socket.close();
          reject(new Error('Terminal WebSocket probe timed out'));
        }
      }, 20000);
      const finish = (value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        socket.close();
        resolve(value);
      };
      socket.onerror = () => {
        if (!settled) {
          settled = true;
          clearTimeout(timeout);
          reject(new Error('Terminal WebSocket probe failed'));
        }
      };
      socket.onmessage = (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
        messages.push(message);
        if (probeMode === 'websocket' && message.type === 'connected') {
          socket.send(JSON.stringify({ type: 'list_tabs' }));
          return;
        }
        if (probeMode === 'websocket' && message.type === 'tab_list') {
          finish({ handshakeStatus: 101, messagesObserved: messages.length });
          return;
        }
        if (probeMode !== 'terminal') return;
        if (message.type === 'connected') {
          socket.send(JSON.stringify({
            type: 'create_tab',
            data: {
              cols: 80,
              rows: 24,
              create_mode: 'always',
              working_directory: '/workspace',
              fallback_working_directory: '/workspace',
            },
          }));
        } else if (message.type === 'tab_created') {
          tabId = message.tab_id;
          if (typeof tabId !== 'string' || !tabId) {
            settled = true;
            clearTimeout(timeout);
            socket.close();
            reject(new Error('Terminal tab creation response is invalid'));
            return;
          }
          socket.send(JSON.stringify({
            type: 'input',
            tab_id: tabId,
            data: { data: `printf '${token}\\n'\\n` },
          }));
        } else if (
          message.type === 'output'
          && typeof message.data?.data === 'string'
          && message.data.data.includes(token)
        ) {
          socket.send(JSON.stringify({ type: 'close_tab', tab_id: tabId }));
          finish({ sessionId: token, roundTrip: 'verified' });
        }
      };
    });
  },
  { platformUrl: options.platformUrl, workspaceId, grant, probeMode: mode },
);

const runAuthenticatedWorkspaceProbe = async (browser, input, options, section) => {
  const loginUser = requiredUser(input.loginUser, 'loginUser');
  if (!options.workspaceId) throw new Error('Workspace identity is required for this browser probe');
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, options, loginUser, input.loginDriver);
  if (exactOrigin(page.url()) !== exactOrigin(options.platformUrl)) {
    throw new Error('OIDC login did not return to Aileron');
  }
  const session = await bootstrapSession(context, options);
  const workspaceId = options.workspaceId;
  try {
    if (section === 'http') {
      const runtimeGrant = await issueExecutionGrant(
        context, options, workspaceId, session, 'workspace-runtime', ['runtime_read'],
      );
      const requests = [
        ['runtime', `${options.platformUrl}/workspaces/${workspaceId}/runtime/health`, runtimeGrant],
        ['browser', `${options.platformUrl}/workspaces/${workspaceId}/browser/health`, null],
        [
          'canvas',
          `${options.platformUrl}/workspaces/${workspaceId}/runtime/api/v1/workspaces/${workspaceId}/canvas/health`,
          runtimeGrant,
        ],
      ];
      const observations = {};
      for (const [name, url, grant] of requests) {
        const headers = { Origin: options.platformUrl, Accept: 'application/json' };
        if (grant) headers.Authorization = `Bearer ${grant}`;
        const response = await context.request.get(url, { headers });
        if (response.status() !== 200) throw new Error(`${name} HTTP probe failed`);
        observations[name] = 200;
      }
      return observations;
    }
    const terminalGrant = await issueExecutionGrant(
      context, options, workspaceId, session, 'workspace-terminal', ['terminal'],
    );
    return await runTerminalWebSocket(page, options, workspaceId, terminalGrant, section);
  } finally {
    await context.close();
  }
};

const REQUIRED_PLATFORM_ADMIN_OPERATIONS = [
  'user_management.manage',
  'marketplace.content.manage',
  'marketplace.registry.manage',
];

export const verifyPlatformAdminAccess = async (context, options) => {
  const headers = { Origin: options.platformUrl, Accept: 'application/json' };
  const sessionResponse = await context.request.get(
    `${options.platformUrl}/api/v1/oauth2/session`,
    { headers },
  );
  if (sessionResponse.status() !== 200) {
    throw new Error('Platform administrator session probe failed');
  }
  const session = await sessionResponse.json();
  const operations = session.user?.allowed_operations;
  if (
    session.user?.platform_role !== 'admin'
    || !Array.isArray(operations)
    || REQUIRED_PLATFORM_ADMIN_OPERATIONS.some((operation) => !operations.includes(operation))
  ) {
    throw new Error('Platform administrator authorization contract is incomplete');
  }

  const adminUsersResponse = await context.request.get(
    `${options.platformUrl}/api/v1/admin/users?page=1&pageSize=1`,
    { headers },
  );
  if (adminUsersResponse.status() !== 200) {
    throw new Error('Platform administrator user-management probe failed');
  }
  const marketplaceCatalogResponse = await context.request.get(
    `${options.platformUrl}/api/v1/marketplace/packages?page=1&pageSize=1`,
    { headers },
  );
  if (marketplaceCatalogResponse.status() !== 200) {
    throw new Error('Platform administrator Marketplace catalog probe failed');
  }

  return {
    platformRole: 'admin',
    requiredOperations: 'verified',
    adminUsersStatus: 200,
    marketplaceCatalogStatus: 200,
  };
};

export const verifyDisabledLoginRejected = async (page, context, options) => {
  const currentPath = safePageLocation(page, options);
  if (currentPath === 'platform') {
    throw new AcceptanceDiagnosticError({
      code: 'admin-disable-login-probe-failed',
      stage: 'disabled-login-rejection',
      currentPath,
      rejectionReason: 'returned-to-platform',
      errorType: 'Error',
    });
  }

  const sessionResponse = await context.request.get(
    `${options.platformUrl}/api/v1/oauth2/session`,
    { headers: { Origin: options.platformUrl, Accept: 'application/json' } },
  );
  const managerSessionStatus = sessionResponse.status();
  if (managerSessionStatus !== 401) {
    throw new AcceptanceDiagnosticError({
      code: 'admin-disable-login-probe-failed',
      stage: 'disabled-login-rejection',
      currentPath,
      rejectionReason: 'manager-session-not-rejected',
      managerSessionStatus,
      errorType: 'Error',
    });
  }
  return {
    platformReturn: 'blocked',
    managerSessionStatus,
  };
};

export const readCanonicalUserSubject = async (context, options) => {
  const response = await context.request.get(
    `${options.platformUrl}/api/v1/oauth2/session`,
    { headers: { Origin: options.platformUrl, Accept: 'application/json' } },
  );
  if (response.status() !== 200) {
    throw new Error('Authenticated Manager session subject probe failed');
  }
  const session = await response.json();
  const subject = session.user?.subject;
  if (
    typeof subject !== 'string'
    || subject.length === 0
    || subject !== subject.trim()
  ) {
    throw new Error('Authenticated Manager session subject is invalid');
  }
  return subject;
};

export const resolveAdminDisableRecovery = ({
  probeError,
  uiRestorationError,
  closeError,
  restoredLoginError,
}) => {
  if (restoredLoginError) {
    const restoredLoginDiagnostic = safeFailureDiagnostic(restoredLoginError);
    const uiRestorationDiagnostic = uiRestorationError
      ? safeFailureDiagnostic(uiRestorationError)
      : null;
    throw new AcceptanceDiagnosticError({
      ...restoredLoginDiagnostic,
      ...(uiRestorationDiagnostic ? {
        uiRestorationStage: uiRestorationDiagnostic.stage,
        ...(uiRestorationDiagnostic.adminConsoleStage
          ? { uiRestorationAdminConsoleStage: uiRestorationDiagnostic.adminConsoleStage }
          : {}),
        uiRestorationErrorType: uiRestorationDiagnostic.errorType,
      } : {}),
    });
  }
  if (probeError) throw probeError;
  if (closeError) throw closeError;
  return {
    restoration: uiRestorationError ? 'verifiedByFreshLogin' : 'reEnabled',
    ...(uiRestorationError ? {
      uiRestorationDiagnostic: safeFailureDiagnostic(uiRestorationError),
    } : {}),
  };
};

const runAdminDisable = async (browser, input, options) => {
  const breakGlassUser = requiredUser(input.breakGlassUser, 'breakGlassUser');
  const adminUser = requiredUser(input.adminUser, 'adminUser');
  const platformAdminUser = requiredUser(input.platformAdminUser, 'platformAdminUser');
  const firstContext = await browser.newContext();
  const firstPage = await firstContext.newPage();
  let canonicalSubject;
  let initialStage = 'initial-login';
  try {
    await login(firstPage, options, breakGlassUser, input.loginDriver);
    if (exactOrigin(firstPage.url()) !== exactOrigin(options.platformUrl)) {
      throw new Error('Target user cannot log in before disable');
    }
    initialStage = 'initial-manager-session';
    canonicalSubject = await readCanonicalUserSubject(firstContext, options);
    buildAdminConsoleUserUrl(options.issuerUrl, options.adminConsoleUrl, canonicalSubject);
  } catch (error) {
    throw adminDisableDiagnosticError(initialStage, firstPage, options, error);
  } finally {
    await firstContext.close();
  }

  let adminConsole = null;
  let probeError;
  let restorationError;
  let closeError;
  let stage = 'disable-user';
  let activePage = null;
  const adminConsoleUserUrl = buildAdminConsoleUserUrl(
    options.issuerUrl, options.adminConsoleUrl, canonicalSubject,
  );
  try {
    adminConsole = await openAdminConsoleUser(
      browser, options, adminUser, canonicalSubject,
    );
    activePage = adminConsole.page;
    const disabledSubject = await setOpenAdminConsoleUserEnabled(
      adminConsole.page, adminConsole.selectedUserId, false, adminConsoleUserUrl,
    );
    if (disabledSubject !== canonicalSubject) {
      throw new Error('Disabled user identity does not match the authenticated subject');
    }

    const secondContext = await browser.newContext();
    try {
      const secondPage = await secondContext.newPage();
      activePage = secondPage;
      stage = 'disabled-login-submit';
      await login(secondPage, options, breakGlassUser, input.loginDriver);
      stage = 'disabled-login-rejection';
      await verifyDisabledLoginRejected(secondPage, secondContext, options);
    } finally {
      await secondContext.close();
    }
  } catch (error) {
    probeError = adminDisableDiagnosticError(stage, activePage, options, error);
  } finally {
    if (adminConsole) {
      try {
        const restoredSubject = await setOpenAdminConsoleUserEnabled(
          adminConsole.page, adminConsole.selectedUserId, true, adminConsoleUserUrl,
        );
        if (restoredSubject !== canonicalSubject) {
          throw new Error('Restored user identity does not match the disabled user');
        }
      } catch (error) {
        restorationError = adminDisableDiagnosticError(
          'restore-user', adminConsole.page, options, error,
        );
      }
      try {
        await adminConsole.context.close();
      } catch (error) {
        closeError = adminDisableDiagnosticError(
          'admin-console-close', adminConsole.page, options,
          adminConsoleStageError('context-close', error),
        );
      }
    }
  }
  const restoredContext = await browser.newContext();
  const restoredPage = await restoredContext.newPage();
  let restoredLoginError;
  try {
    await login(restoredPage, options, breakGlassUser, input.loginDriver);
    if (exactOrigin(restoredPage.url()) !== exactOrigin(options.platformUrl)) {
      throw new Error('Restored break-glass user cannot obtain a new Aileron login');
    }
  } catch (error) {
    restoredLoginError = adminDisableDiagnosticError(
      'restored-login', restoredPage, options, error,
    );
  } finally {
    await restoredContext.close();
  }
  const recovery = resolveAdminDisableRecovery({
    probeError,
    uiRestorationError: restorationError,
    closeError,
    restoredLoginError,
  });
  const platformAdminContext = await browser.newContext();
  let platformAdmin;
  const platformAdminPage = await platformAdminContext.newPage();
  try {
    await login(platformAdminPage, options, platformAdminUser, input.loginDriver);
    if (exactOrigin(platformAdminPage.url()) !== exactOrigin(options.platformUrl)) {
      throw new Error('Platform administrator cannot obtain a new Aileron login');
    }
    platformAdmin = await verifyPlatformAdminAccess(platformAdminContext, options);
  } catch (error) {
    throw adminDisableDiagnosticError('platform-admin-verification', platformAdminPage, options, error);
  } finally {
    await platformAdminContext.close();
  }
  return {
    initialLogin: 'accepted',
    disabledLogin: 'rejected',
    ...recovery,
    restoredLogin: 'accepted',
    platformAdmin,
  };
};

const main = async () => {
  const section = option('--section');
  const hasAdminConsoleUrl = process.argv.includes('--admin-console-url');
  if (section !== 'adminDisableLogin' && hasAdminConsoleUrl) {
    throw new Error('Admin Console URL is valid only for adminDisableLogin');
  }
  const options = {
    platformUrl: option('--platform-url').replace(/\/$/, ''),
    issuerUrl: option('--issuer-url').replace(/\/$/, ''),
    clientId: option('--client-id'),
    runId: option('--run-id'),
    workspaceId: process.argv.includes('--workspace-id') ? option('--workspace-id') : null,
    adminConsoleUrl: section === 'adminDisableLogin' ? option('--admin-console-url') : null,
  };
  if (section === 'adminDisableLogin') {
    buildAdminConsoleUrl(options.issuerUrl, options.adminConsoleUrl);
  }
  const metadata = await loadOidcDiscovery(options.issuerUrl);
  options.authorizationEndpoint = metadata.authorizationEndpoint;
  const input = JSON.parse(fs.readFileSync(INPUT_PATH, 'utf8'));
  if (input.schemaVersion !== 'aileron-browser-input/v2') throw new Error('Unsupported private browser input');
  input.loginDriver = requiredLoginDriver(input.loginDriver);
  const browser = await chromium.launch({ headless: true });
  try {
    const observation = section === 'oidcWorkspace'
      ? await runOidcWorkspace(browser, input, options)
      : section === 'workspaceLifecycle'
        ? await runWorkspaceLifecycle(browser, input, options)
        : section === 'browser'
          ? await runBrowserSession(browser, input, options)
          : section === 'adminDisableLogin'
            ? await runAdminDisable(browser, input, options)
            : await runAuthenticatedWorkspaceProbe(browser, input, options, section);
    process.stdout.write(`${JSON.stringify(observation)}\n`);
  } finally {
    await browser.close();
  }
};

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  try {
    await main();
  } catch (error) {
    const diagnostic = safeFailureDiagnostic(error);
    process.stderr.write(`acceptance_error=${JSON.stringify(diagnostic)}\n`);
    process.exitCode = 1;
  }
}
