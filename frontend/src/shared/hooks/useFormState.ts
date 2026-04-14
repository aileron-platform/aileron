import { useState, useEffect, useCallback } from 'react';

/**
 * 通用表單狀態管理 hook
 *
 * @param buildInitialState - 從初始值建立表單狀態的函數
 * @param initialValue - 初始值（編輯模式時傳入）
 * @param open - Dialog 是否開啟
 */
export function useFormState<TForm, TInitial>(
  buildInitialState: (value?: TInitial | null) => TForm,
  initialValue: TInitial | null | undefined,
  open: boolean
) {
  const [formState, setFormState] = useState<TForm>(() => buildInitialState(initialValue));
  const [submitting, setSubmitting] = useState(false);

  // 當 dialog 開啟或初始值改變時重置表單
  useEffect(() => {
    if (open) {
      setFormState(buildInitialState(initialValue));
      setSubmitting(false);
    }
  }, [open, initialValue, buildInitialState]);

  const updateField = useCallback(<K extends keyof TForm>(field: K, value: TForm[K]) => {
    setFormState((prev) => ({ ...prev, [field]: value }));
  }, []);

  const resetForm = useCallback(() => {
    setFormState(buildInitialState(initialValue));
    setSubmitting(false);
  }, [buildInitialState, initialValue]);

  return {
    formState,
    setFormState,
    updateField,
    submitting,
    setSubmitting,
    resetForm,
  };
}
