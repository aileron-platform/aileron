import { expect, test, type Locator, type Page } from '@playwright/test';

test.setTimeout(90_000);

const products = ['workspace', 'knowledge-base', 'marketplace'] as const;
const modes = ['changes', 'history'] as const;
const states = ['empty', 'loading', 'error'] as const;
const edges = ['top-left', 'top-right', 'bottom-left', 'bottom-right'] as const;

type Product = typeof products[number];

const fixtureUrl = (parameters: Record<string, string>) => {
  const search = new URLSearchParams(parameters);
  return `/e2e/fixtures/?${search.toString()}`;
};

const expectNoDocumentOverflow = async (page: Page) => {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
};

const expectInsideViewport = async (page: Page, locator: Locator) => {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  if (!box || !viewport) return;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
};

const expectDescendantsInside = async (container: Locator) => {
  const overflow = await container.evaluate((containerRoot) => {
    const root = containerRoot.closest<HTMLElement>('[data-shell-region]') ?? containerRoot;
    const rootRect = root.getBoundingClientRect();
    return [...root.querySelectorAll<HTMLElement>('*')]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return style.position !== 'fixed'
          && rect.width > 0
          && rect.height > 0
          && (
            rect.left < rootRect.left - 1
            || rect.right > rootRect.right + 1
            || rect.top < rootRect.top - 1
            || rect.bottom > rootRect.bottom + 1
          );
      })
      .map((element) => ({
        testId: element.dataset.testid ?? null,
        tagName: element.tagName,
        text: element.textContent?.trim().slice(0, 80) ?? '',
      }));
  });
  expect(overflow).toEqual([]);
};

const expectInsideOwner = async (owner: Locator, child: Locator) => {
  await expect(owner).toBeVisible();
  await expect(child).toBeVisible();
  const ownerBox = await owner.boundingBox();
  const childBox = await child.boundingBox();
  expect(ownerBox).not.toBeNull();
  expect(childBox).not.toBeNull();
  if (!ownerBox || !childBox) return;
  expect(childBox.x).toBeGreaterThanOrEqual(ownerBox.x - 1);
  expect(childBox.y).toBeGreaterThanOrEqual(ownerBox.y - 1);
  expect(childBox.x + childBox.width).toBeLessThanOrEqual(ownerBox.x + ownerBox.width + 1);
  expect(childBox.y + childBox.height).toBeLessThanOrEqual(ownerBox.y + ownerBox.height + 1);
};

const getProductPresentation = (page: Page, product: Product) => page.getByTestId({
  workspace: 'workspace-version-control-presentation',
  'knowledge-base': 'knowledge-base-version-control-presentation',
  marketplace: 'marketplace-version-control-presentation',
}[product]);

const getProductSidebar = (page: Page, product: Product) => page.getByTestId(
  `${product}-version-control-sidebar`,
);

const getProductMain = (page: Page, product: Product) => page.getByTestId(
  `${product}-version-control-main`,
);

test('workspace ProductShell exposes only the requested semantic regions', async ({ page }) => {
  await page.goto(fixtureUrl({
    product: 'workspace',
    shell: 'product',
    mode: 'changes',
    state: 'content',
  }));

  const presentation = getProductPresentation(page, 'workspace');
  await expect(presentation).toBeVisible();
  await expect(presentation.locator('[data-shell-region="navigation"]')).toHaveCount(0);
  await expect(presentation.locator('[data-shell-region="navigator"]')).toHaveCount(1);
  await expect(presentation.locator('[data-shell-region="main"]')).toHaveCount(1);
  await expect(presentation.locator('[data-shell-region="companion"]')).toHaveCount(0);
  await expectInsideOwner(
    presentation.locator('[data-shell-region="navigator"]'),
    page.getByTestId('workspace-version-control-sidebar'),
  );
  await expectInsideOwner(
    presentation.locator('[data-shell-region="main"]'),
    page.getByTestId('workspace-version-control-main'),
  );
  await expectNoDocumentOverflow(page);
});

test('all product workbenches expose the same ProductShell region contract', async ({ page }) => {
  for (const product of products) {
    const parameters: Record<string, string> = {
      product,
      mode: 'changes',
      state: 'content',
    };
    if (product === 'workspace') {
      parameters.shell = 'product';
    }
    await page.goto(fixtureUrl(parameters));

    await expect(page.getByTestId('product-shell')).toHaveCount(1);
    const regions = await page.locator('[data-shell-region]').evaluateAll((elements) => (
      elements.map(element => element.getAttribute('data-shell-region'))
    ));
    expect(regions).toEqual(['navigator', 'main']);
  }
});

for (const product of products) {
  for (const mode of modes) {
    test(`${product} ${mode} visual contract`, async ({ page }) => {
      await page.goto(fixtureUrl({
        product,
        mode,
        state: 'content',
        readOnly: '1',
        conflict: '1',
        multi: '1',
      }));

      const presentation = getProductPresentation(page, product);
      await expect(presentation).toBeVisible();
      await expect(page.getByText('component-with-a-long-name.tsx', { exact: true })).toBeVisible();
      if (product === 'workspace' && mode === 'changes') {
        await expect(page.getByTestId('workspace-worktree-extension')).toBeVisible();
      } else {
        await expect(page.getByTestId('workspace-worktree-extension')).toHaveCount(0);
      }
      if (product === 'marketplace') {
        await expect(presentation.getByRole('tablist')).toHaveCount(0);
        await expect(page.getByTestId('product-shell')).toBeVisible();
      }
      const sidebar = getProductSidebar(page, product);
      const main = getProductMain(page, product);
      const branchTrigger = sidebar.getByRole('button', { name: /feature\/unified-version-control/ });
      await expectInsideOwner(sidebar, branchTrigger);
      await expectDescendantsInside(sidebar);
      await expectDescendantsInside(main);
      await expectNoDocumentOverflow(page);
      await expect(page).toHaveScreenshot(`${product}-${mode}.png`, { fullPage: true });
    });
  }

  test(`${product} production layout controls and async states`, async ({ page }) => {
    const parameters: Record<string, string> = {
      product,
      mode: 'changes',
      state: 'content',
    };
    if (product === 'workspace') {
      parameters.shell = 'product';
    }
    await page.goto(fixtureUrl(parameters));
    await expect(getProductPresentation(page, product)).toBeVisible();
    let sidebar = getProductSidebar(page, product);

    await sidebar.getByRole('button', { name: 'Git actions' }).click();
    const worktreeAction = page.getByRole('menuitem', { name: 'Worktree settings...' });
    if (product === 'workspace') {
      await expect(worktreeAction).toBeVisible();
    } else {
      await expect(worktreeAction).toHaveCount(0);
    }
    await page.keyboard.press('Escape');

    if (product === 'knowledge-base' || product === 'marketplace') {
      const initialBox = await sidebar.boundingBox();
      expect(initialBox).not.toBeNull();
      const expectedInitialWidth = 270;
      expect(initialBox?.width).toBeGreaterThanOrEqual(expectedInitialWidth - 1);
      expect(initialBox?.width).toBeLessThanOrEqual(expectedInitialWidth);
      const navigatorRegion = page.locator('[data-shell-region="navigator"]');
      const handle = navigatorRegion.getByRole('separator');
      const handleBox = await handle.boundingBox();
      expect(handleBox).not.toBeNull();
      if (handleBox) {
        await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + 80);
        await page.mouse.down();
        await expect(page.locator('body')).toHaveClass(/cursor-col-resize/);
        await page.mouse.move(handleBox.x + 100, handleBox.y + 80, { steps: 10 });
        await expect.poll(async () => (await sidebar.boundingBox())?.width ?? 0).toBeGreaterThan(
          initialBox?.width ?? 0,
        );
        await page.mouse.up();
      }
      const resizedBox = await sidebar.boundingBox();
      expect(resizedBox && initialBox && resizedBox.width).toBeGreaterThan(initialBox?.width ?? 0);
      await expectDescendantsInside(navigatorRegion);
      await expectNoDocumentOverflow(page);

      await navigatorRegion.getByRole('button', { name: 'Collapse sidebar' }).click();
      await expect(navigatorRegion).toHaveCSS('width', '64px');
      await expectDescendantsInside(navigatorRegion);
      sidebar = navigatorRegion;
    } else {
      await expect(sidebar.getByRole('separator')).toHaveCount(0);
      await expect(sidebar.getByRole('button', { name: 'Collapse sidebar' })).toHaveCount(0);
    }

    if (product === 'marketplace') {
      const navigatorRegion = page.locator('[data-shell-region="navigator"]');
      await navigatorRegion.getByRole('button', { name: 'Expand sidebar' }).click();
      await expect(navigatorRegion).toHaveCSS('width', '352px');
      const historyButton = page.getByTestId('marketplace-version-control-mode-actions').getByRole('button').nth(1);
      await historyButton.click();
      await expect(historyButton).toHaveAttribute('aria-pressed', 'true');
      sidebar = getProductSidebar(page, product);
    }

    if (product === 'workspace') {
      const presentationBox = await getProductPresentation(page, product).boundingBox();
      const sidebarBox = await page.locator('[data-shell-region="navigator"]').boundingBox();
      expect(presentationBox).not.toBeNull();
      expect(sidebarBox).not.toBeNull();
      expect(sidebarBox?.width).toBe((presentationBox?.width ?? 0) / 2);
      await expect(page.getByTestId('shared-version-control-workbench')).toHaveCount(0);
    }

    await expectDescendantsInside(sidebar);
    await expectNoDocumentOverflow(page);

    for (const fixtureState of states) {
      await page.goto(fixtureUrl({ product, mode: 'changes', state: fixtureState }));
      await expect(getProductPresentation(page, product)).toBeVisible();
      if (fixtureState === 'loading') {
        await expect(page.getByTestId('fixture-loading')).toHaveAttribute('aria-busy', 'true');
      } else if (fixtureState === 'error') {
        await expect(page.getByTestId('fixture-error')).toBeVisible();
      }
      await expectDescendantsInside(getProductSidebar(page, product));
      await expectNoDocumentOverflow(page);
    }
  });
}

test('context menus stay inside all four viewport edges', async ({ page }) => {
  for (const product of products) {
    await page.goto(fixtureUrl({ product, surface: 'menu' }));
    await expect(getProductPresentation(page, product)).toBeVisible();
    for (const edge of edges) {
      await page.getByTestId(`edge-trigger-${edge}`).click({ button: 'right' });
      const menu = page.getByTestId(`edge-menu-${edge}`);
      await expectInsideViewport(page, menu);
      await page.keyboard.press('Escape');
    }
    await expectNoDocumentOverflow(page);
  }
});

test('branch selector collision stays inside viewport', async ({ page }) => {
  for (const product of products) {
    await page.goto(fixtureUrl({ product, mode: 'changes', state: 'content' }));
    const sidebar = getProductSidebar(page, product);
    await sidebar.getByRole('button', { name: /feature\/unified-version-control/ }).click();
    const branchPopup = page.getByRole('menu', { name: /feature\/unified-version-control/ });
    await expectInsideViewport(page, branchPopup);
    await expectNoDocumentOverflow(page);
  }
});

for (const dialog of ['confirm', 'form', 'setup'] as const) {
  test(`${dialog} dialog stays inside viewport`, async ({ page }) => {
    for (const product of products) {
      await page.goto(fixtureUrl({ product, surface: 'dialog', dialog }));
      await expect(getProductPresentation(page, product)).toBeVisible();
      if (dialog === 'setup') {
        await page.getByTestId('fixture-setup').getByRole('button').last().click();
      } else {
        await page.getByTestId('fixture-dialog-trigger').click();
      }
      await expectInsideViewport(page, page.getByRole('dialog'));
      await expectNoDocumentOverflow(page);
    }
  });
}
