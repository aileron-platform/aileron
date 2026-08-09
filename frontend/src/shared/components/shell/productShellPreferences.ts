import type {
  ProductShellCompanionRegion,
  ProductShellPreferences,
  ProductShellRegionBehavior,
} from './productShellTypes';

export const PRODUCT_SHELL_COLLAPSED_COLUMN_WIDTH = 64;
export const PRODUCT_SHELL_COMPACT_COMPANION_WIDTH = 48;
export const PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH = 320;

export const PRODUCT_SHELL_DEFAULT_REGION_BEHAVIOR: ProductShellRegionBehavior = {
  collapsible: true,
  resizable: true,
  defaultWidth: 256,
  minWidth: 220,
  maxWidth: 600,
};

export const PRODUCT_SHELL_DEFAULT_NAVIGATOR_BEHAVIOR: ProductShellRegionBehavior = {
  ...PRODUCT_SHELL_DEFAULT_REGION_BEHAVIOR,
  defaultWidth: 320,
};

export const PRODUCT_SHELL_DEFAULT_COMPANION = {
  ...PRODUCT_SHELL_DEFAULT_REGION_BEHAVIOR,
  defaultWidth: 320,
  defaultHeight: 240,
  minHeight: 160,
  maxHeight: 520,
  mainMinHeight: PRODUCT_SHELL_MIN_MAIN_CONTENT_WIDTH,
} as const;

export interface ProductShellResolvedPreferences {
  navigation: { collapsed: boolean; width: number };
  navigator: { collapsed: boolean; width: number };
  companion: {
    collapsed: boolean;
    width: number;
    height: number;
    placement: 'side' | 'bottom';
  };
}

const isFiniteNumber = (value: unknown): value is number => (
  typeof value === 'number' && Number.isFinite(value)
);

const isValidRange = (min: unknown, max: unknown): min is number => (
  isFiniteNumber(min) && isFiniteNumber(max) && min <= max
);

export const assertProductShellRegionBehavior = (
  behavior: ProductShellRegionBehavior,
  regionName: string,
): void => {
  if (
    typeof behavior.collapsible !== 'boolean'
    || typeof behavior.resizable !== 'boolean'
    || !isFiniteNumber(behavior.defaultWidth)
    || !isValidRange(behavior.minWidth, behavior.maxWidth)
    || behavior.defaultWidth < behavior.minWidth
    || behavior.defaultWidth > behavior.maxWidth
  ) {
    throw new Error(`Invalid ProductShell ${regionName} region behavior limits`);
  }
};

export const assertProductShellCompanionRegion = (
  companion: ProductShellCompanionRegion,
): void => {
  assertProductShellRegionBehavior(companion.side, 'companion');
  const { defaultHeight, minHeight, maxHeight, mainMinHeight } = companion.bottom;
  if (
    !isFiniteNumber(defaultHeight)
    || !isValidRange(minHeight, maxHeight)
    || defaultHeight < minHeight
    || defaultHeight > maxHeight
    || !isFiniteNumber(mainMinHeight)
    || mainMinHeight < 0
  ) {
    throw new Error('Invalid ProductShell companion height limits');
  }
};

export const clampProductShellValue = (
  value: number,
  min: number,
  max: number,
): number => Math.max(min, Math.min(max, value));

const resolveColumn = (
  value: ProductShellPreferences['navigation'] | ProductShellPreferences['navigator'],
  behavior: ProductShellRegionBehavior,
): { collapsed: boolean; width: number } => ({
  collapsed: value?.collapsed === true,
  width: clampProductShellValue(
    isFiniteNumber(value?.width) ? value.width : behavior.defaultWidth,
    behavior.minWidth,
    behavior.maxWidth,
  ),
});

export const resolveProductShellPreferences = (
  value: ProductShellPreferences | null | undefined,
  navigationBehavior: ProductShellRegionBehavior = PRODUCT_SHELL_DEFAULT_REGION_BEHAVIOR,
  navigatorBehavior: ProductShellRegionBehavior = PRODUCT_SHELL_DEFAULT_NAVIGATOR_BEHAVIOR,
  companionRegion?: ProductShellCompanionRegion,
): ProductShellResolvedPreferences => {
  const companionBehavior = companionRegion?.side ?? PRODUCT_SHELL_DEFAULT_COMPANION;
  const companionBottom = companionRegion?.bottom ?? PRODUCT_SHELL_DEFAULT_COMPANION;
  const companionValue = value?.companion;
  return {
    navigation: resolveColumn(value?.navigation, navigationBehavior),
    navigator: resolveColumn(value?.navigator, navigatorBehavior),
    companion: {
      collapsed: companionValue?.collapsed === true,
      width: clampProductShellValue(
        isFiniteNumber(companionValue?.width)
          ? companionValue.width
          : companionBehavior.defaultWidth,
        companionBehavior.minWidth,
        companionBehavior.maxWidth,
      ),
      height: clampProductShellValue(
        isFiniteNumber(companionValue?.height)
          ? companionValue.height
          : companionBottom.defaultHeight,
        companionBottom.minHeight,
        companionBottom.maxHeight,
      ),
      placement: companionValue?.placement === 'bottom' ? 'bottom' : 'side',
    },
  };
};

export const toProductShellPreferences = (
  value: ProductShellResolvedPreferences,
): ProductShellPreferences => ({
  navigation: value.navigation,
  navigator: value.navigator,
  companion: value.companion,
});
