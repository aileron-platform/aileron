import { expect, test } from '@playwright/test';

const entryFixtureUrl = (entryState: string) => {
  const search = new URLSearchParams({
    surface: 'entry',
    entryState,
  });
  return `/e2e/fixtures/?${search.toString()}`;
};

test('keeps the navigation geometry while the workspace entry panel appears', async ({ page }) => {
  await page.goto(entryFixtureUrl('pending'));

  const navigation = page.getByTestId('entry-navigation');
  await expect(navigation).toBeVisible();
  const initialBox = await navigation.boundingBox();
  await expect(page.getByTestId('entry-progress-panel')).toBeVisible();
  await expect(page.getByTestId('entry-frame')).toHaveCount(1);
  const visibleBox = await navigation.boundingBox();

  expect(initialBox).not.toBeNull();
  expect(visibleBox).not.toBeNull();
  expect(visibleBox?.x).toBe(initialBox?.x);
  expect(visibleBox?.y).toBe(initialBox?.y);
  await expect(page).toHaveTitle('Product Shell Fixture');
});

test('exposes only allowed recovery actions and transitions after start', async ({ page }) => {
  await page.goto(entryFixtureUrl('stopped'));

  const panel = page.getByTestId('entry-progress-panel');
  await expect(panel).toBeVisible();
  await expect(page.getByTestId('entry-frame')).toHaveCount(1);
  await expect(panel.getByRole('button', { name: 'Start workspace' })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Rebuild execution environment' })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Return to workspaces' })).toBeVisible();
  await expect(page.getByTestId('entry-ready-content')).toHaveCount(0);

  await panel.getByRole('button', { name: 'Start workspace' }).click();
  await expect(page.getByTestId('entry-ready-content')).toBeVisible();
  await expect(page.getByTestId('entry-action-log')).toHaveAttribute('data-actions', 'start');
});

test('uses a stable reason code for uncertain availability and supports refresh', async ({ page }) => {
  await page.goto(entryFixtureUrl('uncertain'));

  const panel = page.getByTestId('entry-progress-panel');
  await expect(panel).toBeVisible();
  await expect(page.getByTestId('entry-frame')).toHaveCount(1);
  await expect(panel.getByText('WORKSPACE_AVAILABILITY_UNCERTAIN')).toBeVisible();
  await expect(page.getByText('controller-internal-details')).toHaveCount(0);

  await panel.getByRole('button', { name: 'Check again' }).click();
  await expect(page.getByTestId('entry-ready-content')).toBeVisible();
  await expect(page.getByTestId('entry-action-log')).toHaveAttribute('data-actions', 'refresh');
});
