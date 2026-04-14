/**
 * 自定義斷言輔助函數
 * 提供常見的測試斷言封裝
 */

import { screen, within } from '@testing-library/react';
import { expect } from 'vitest';

/**
 * 斷言元素存在
 */
export const expectElementToExist = (text: string | RegExp) => {
  expect(screen.getByText(text)).toBeInTheDocument();
};

/**
 * 斷言元素不存在
 */
export const expectElementNotToExist = (text: string | RegExp) => {
  expect(screen.queryByText(text)).not.toBeInTheDocument();
};

/**
 * 斷言元素可見
 */
export const expectElementToBeVisible = (text: string | RegExp) => {
  expect(screen.getByText(text)).toBeVisible();
};

/**
 * 斷言元素隱藏
 */
export const expectElementToBeHidden = (text: string | RegExp) => {
  const element = screen.queryByText(text);
  if (element) {
    expect(element).not.toBeVisible();
  } else {
    expect(element).not.toBeInTheDocument();
  }
};

/**
 * 斷言按鈕啟用
 */
export const expectButtonToBeEnabled = (buttonText: string | RegExp) => {
  expect(screen.getByRole('button', { name: buttonText })).toBeEnabled();
};

/**
 * 斷言按鈕禁用
 */
export const expectButtonToBeDisabled = (buttonText: string | RegExp) => {
  expect(screen.getByRole('button', { name: buttonText })).toBeDisabled();
};

/**
 * 斷言輸入框值
 */
export const expectInputValue = (labelText: string | RegExp, value: string) => {
  const input = screen.getByLabelText(labelText) as HTMLInputElement;
  expect(input.value).toBe(value);
};

/**
 * 斷言輸入框為空
 */
export const expectInputToBeEmpty = (labelText: string | RegExp) => {
  const input = screen.getByLabelText(labelText) as HTMLInputElement;
  expect(input.value).toBe('');
};

/**
 * 斷言核取方塊已勾選
 */
export const expectCheckboxToBeChecked = (labelText: string | RegExp) => {
  expect(screen.getByLabelText(labelText)).toBeChecked();
};

/**
 * 斷言核取方塊未勾選
 */
export const expectCheckboxNotToBeChecked = (labelText: string | RegExp) => {
  expect(screen.getByLabelText(labelText)).not.toBeChecked();
};

/**
 * 斷言元素有特定類別
 */
export const expectElementToHaveClass = (
  text: string | RegExp,
  className: string
) => {
  expect(screen.getByText(text)).toHaveClass(className);
};

/**
 * 斷言元素有特定屬性
 */
export const expectElementToHaveAttribute = (
  text: string | RegExp,
  attribute: string,
  value?: string
) => {
  if (value !== undefined) {
    expect(screen.getByText(text)).toHaveAttribute(attribute, value);
  } else {
    expect(screen.getByText(text)).toHaveAttribute(attribute);
  }
};

/**
 * 斷言列表長度
 */
export const expectListLength = (testId: string, length: number) => {
  const list = screen.getByTestId(testId);
  const items = within(list).getAllByRole('listitem');
  expect(items).toHaveLength(length);
};

/**
 * 斷言表格行數
 */
export const expectTableRowCount = (testId: string, count: number) => {
  const table = screen.getByTestId(testId);
  const rows = within(table).getAllByRole('row');
  // 減 1 是因為不計算表頭
  expect(rows.length - 1).toBe(count);
};

/**
 * 斷言元素有焦點
 */
export const expectElementToHaveFocus = (text: string | RegExp) => {
  expect(screen.getByText(text)).toHaveFocus();
};

/**
 * 斷言表單驗證錯誤
 */
export const expectValidationError = (errorText: string | RegExp) => {
  expect(screen.getByText(errorText)).toBeInTheDocument();
};

/**
 * 斷言載入中狀態
 */
export const expectLoadingState = () => {
  expect(
    screen.getByText(/loading|載入中|讀取中/i)
  ).toBeInTheDocument();
};

/**
 * 斷言錯誤訊息
 */
export const expectErrorMessage = (message?: string | RegExp) => {
  if (message) {
    expect(screen.getByText(message)).toBeInTheDocument();
  } else {
    expect(screen.getByText(/error|錯誤/i)).toBeInTheDocument();
  }
};

/**
 * 斷言成功訊息
 */
export const expectSuccessMessage = (message?: string | RegExp) => {
  if (message) {
    expect(screen.getByText(message)).toBeInTheDocument();
  } else {
    expect(screen.getByText(/success|成功/i)).toBeInTheDocument();
  }
};

/**
 * 斷言 API 呼叫次數
 */
export const expectApiCallCount = (mockFn: any, count: number) => {
  expect(mockFn).toHaveBeenCalledTimes(count);
};

/**
 * 斷言 API 呼叫參數
 */
export const expectApiCallWith = (mockFn: any, ...args: any[]) => {
  expect(mockFn).toHaveBeenCalledWith(...args);
};

/**
 * 斷言陣列包含元素
 */
export const expectArrayToContain = <T>(array: T[], element: T) => {
  expect(array).toContain(element);
};

/**
 * 斷言物件包含屬性
 */
export const expectObjectToContain = <T extends object>(
  obj: T,
  subset: Partial<T>
) => {
  expect(obj).toMatchObject(subset);
};
