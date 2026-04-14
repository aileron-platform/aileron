import { useState, useCallback } from 'react';

export interface ValidationRule {
  (value: any): string | null;
}

export interface ValidationConfig {
  [key: string]: ValidationRule;
}

export interface ValidationErrors {
  [key: string]: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationErrors;
}

export const commonValidationRules = {
  required: (message: string): ValidationRule => (value) => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return message;
    }
    return null;
  },

  minLength: (length: number, message: string): ValidationRule => (value) => {
    if (typeof value === 'string' && value.length < length) {
      return message;
    }
    return null;
  },

  maxLength: (length: number, message: string): ValidationRule => (value) => {
    if (typeof value === 'string' && value.length > length) {
      return message;
    }
    return null;
  },

  url: (message: string): ValidationRule => (value) => {
    if (value && typeof value === 'string') {
      try {
        new URL(value);
        return null;
      } catch {
        return message;
      }
    }
    return null;
  }
};

export function useFormValidation(config: ValidationConfig) {
  const [errors, setErrors] = useState<ValidationErrors>({});

  const validateForm = useCallback((data: any): ValidationResult => {
    const newErrors: ValidationErrors = {};
    let isValid = true;

    Object.keys(config).forEach(field => {
      const rule = config[field];
      const error = rule(data[field]);
      if (error) {
        newErrors[field] = error;
        isValid = false;
      }
    });

    setErrors(newErrors);
    return { isValid, errors: newErrors };
  }, [config]);

  const clearErrors = useCallback(() => {
    setErrors({});
  }, []);

  const clearFieldError = useCallback((field: string) => {
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[field];
      return newErrors;
    });
  }, []);

  return {
    errors,
    validateForm,
    clearErrors,
    clearFieldError
  };
}