import { useState, useCallback } from 'react';

export type ValidationRule<T> = (value: T) => string | undefined;

export type ValidationRules<TForm> = {
  [K in keyof TForm]?: ValidationRule<TForm[K]>;
};

export type ValidationErrors<TForm> = {
  [K in keyof TForm]?: string;
};

/**
 * 通用表單驗證 hook
 */
export function useFormValidation<TForm extends Record<string, unknown>>(
  rules: ValidationRules<TForm>
) {
  const [errors, setErrors] = useState<ValidationErrors<TForm>>({});

  const validate = useCallback(
    (formState: TForm): boolean => {
      const nextErrors: ValidationErrors<TForm> = {};

      for (const field of Object.keys(rules) as Array<keyof TForm>) {
        const rule = rules[field];
        if (rule) {
          const error = rule(formState[field]);
          if (error) {
            nextErrors[field] = error;
          }
        }
      }

      setErrors(nextErrors);
      return Object.keys(nextErrors).length === 0;
    },
    [rules]
  );

  const clearErrors = useCallback(() => {
    setErrors({});
  }, []);

  const setFieldError = useCallback((field: keyof TForm, error: string | undefined) => {
    setErrors((prev) => {
      if (error) {
        return { ...prev, [field]: error };
      }
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }, []);

  return {
    errors,
    validate,
    clearErrors,
    setFieldError,
  };
}

/**
 * 常用的驗證規則工廠
 */
export const validators = {
  required: (message: string) => (value: unknown) => {
    if (typeof value === 'string' && !value.trim()) {
      return message;
    }
    if (value === null || value === undefined) {
      return message;
    }
    return undefined;
  },

  minLength: (min: number, message: string) => (value: string) => {
    if (value.trim().length < min) {
      return message;
    }
    return undefined;
  },

  pattern: (regex: RegExp, message: string) => (value: string) => {
    if (!regex.test(value)) {
      return message;
    }
    return undefined;
  },
};
