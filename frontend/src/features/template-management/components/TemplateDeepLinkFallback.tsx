import React, { useEffect } from 'react';
import { matchPath, useLocation, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/shared/constants/routes';
import { useTemplateManagementContext } from '../providers/TemplateManagementProvider';

const RESERVED_TEMPLATE_ROUTE_SEGMENTS = new Set(['new', 'settings']);

export interface TemplateDeepLinkFallbackProps {
  children: React.ReactNode;
}

export const TemplateDeepLinkFallback: React.FC<TemplateDeepLinkFallbackProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { templates, isLoading } = useTemplateManagementContext();

  useEffect(() => {
    if (isLoading) return;

    const detailMatch = matchPath('/templates/templates/:templateId', location.pathname);
    const editMatch = matchPath('/templates/templates/:templateId/edit', location.pathname);
    const templateId = detailMatch?.params.templateId ?? editMatch?.params.templateId;

    if (!templateId) return;
    if (RESERVED_TEMPLATE_ROUTE_SEGMENTS.has(templateId)) return;
    if (templates.some((template) => template.id === templateId)) return;

    navigate(ROUTES.TEMPLATE_CENTER, { replace: true });
  }, [isLoading, location.pathname, navigate, templates]);

  return <>{children}</>;
};

export default TemplateDeepLinkFallback;
