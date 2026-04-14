/**
 * 使用者互動輔助函數
 * 提供常見的使用者操作封裝
 */

import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

/**
 * 點擊按鈕
 */
export const clickButton = async (buttonText: string | RegExp) => {
  const button = screen.getByRole('button', { name: buttonText });
  await userEvent.click(button);
  return button;
};

/**
 * 點擊連結
 */
export const clickLink = async (linkText: string | RegExp) => {
  const link = screen.getByRole('link', { name: linkText });
  await userEvent.click(link);
  return link;
};

/**
 * 填寫輸入框
 */
export const fillInput = async (labelText: string | RegExp, value: string) => {
  const input = screen.getByLabelText(labelText) as HTMLInputElement;
  await userEvent.clear(input);
  await userEvent.type(input, value);
  return input;
};

/**
 * 填寫文字區域
 */
export const fillTextarea = async (labelText: string | RegExp, value: string) => {
  const textarea = screen.getByLabelText(labelText) as HTMLTextAreaElement;
  await userEvent.clear(textarea);
  await userEvent.type(textarea, value);
  return textarea;
};

/**
 * 選擇下拉選項
 */
export const selectOption = async (labelText: string | RegExp, optionText: string) => {
  const select = screen.getByLabelText(labelText) as HTMLSelectElement;
  await userEvent.selectOptions(select, optionText);
  return select;
};

/**
 * 勾選核取方塊
 */
export const checkCheckbox = async (labelText: string | RegExp) => {
  const checkbox = screen.getByLabelText(labelText) as HTMLInputElement;
  if (!checkbox.checked) {
    await userEvent.click(checkbox);
  }
  return checkbox;
};

/**
 * 取消勾選核取方塊
 */
export const uncheckCheckbox = async (labelText: string | RegExp) => {
  const checkbox = screen.getByLabelText(labelText) as HTMLInputElement;
  if (checkbox.checked) {
    await userEvent.click(checkbox);
  }
  return checkbox;
};

/**
 * 選擇單選按鈕
 */
export const selectRadio = async (labelText: string | RegExp) => {
  const radio = screen.getByLabelText(labelText) as HTMLInputElement;
  await userEvent.click(radio);
  return radio;
};

/**
 * 提交表單
 */
export const submitForm = async (formTestId?: string) => {
  const form = formTestId
    ? screen.getByTestId(formTestId)
    : screen.getByRole('form');
  fireEvent.submit(form);
  return form;
};

/**
 * 等待元素出現
 */
export const waitForElement = async (
  text: string | RegExp,
  options?: { timeout?: number }
) => {
  return waitFor(() => screen.getByText(text), options);
};

/**
 * 等待元素消失
 */
export const waitForElementToBeRemoved = async (
  text: string | RegExp,
  options?: { timeout?: number }
) => {
  const element = screen.getByText(text);
  return waitFor(() => expect(element).not.toBeInTheDocument(), options);
};

/**
 * 滑鼠懸停
 */
export const hoverElement = async (element: HTMLElement) => {
  await userEvent.hover(element);
};

/**
 * 滑鼠離開
 */
export const unhoverElement = async (element: HTMLElement) => {
  await userEvent.unhover(element);
};

/**
 * 按下鍵盤按鍵
 */
export const pressKey = async (key: string) => {
  await userEvent.keyboard(key);
};

/**
 * 上傳檔案
 */
export const uploadFile = async (inputTestId: string, file: File) => {
  const input = screen.getByTestId(inputTestId) as HTMLInputElement;
  await userEvent.upload(input, file);
  return input;
};

/**
 * 拖放操作
 */
export const dragAndDrop = (
  source: HTMLElement,
  target: HTMLElement
) => {
  fireEvent.dragStart(source);
  fireEvent.dragEnter(target);
  fireEvent.dragOver(target);
  fireEvent.drop(target);
  fireEvent.dragEnd(source);
};

/**
 * 滾動到元素
 */
export const scrollToElement = (element: HTMLElement) => {
  fireEvent.scroll(element);
};

/**
 * 創建 user event 實例
 */
export const createUser = () => userEvent.setup();
