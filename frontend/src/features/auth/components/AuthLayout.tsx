import React from 'react';
import { Link } from 'react-router-dom';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';

interface AuthLayoutProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  backToDashboard?: boolean;
}

export const AuthLayout: React.FC<AuthLayoutProps> = props => {
  const { title, description, children, footer, backToDashboard = false } = props;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100">
      <div className="flex min-h-screen items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center">
            <Link
              to={backToDashboard ? '/workspaces' : '/'}
              className="inline-flex items-center justify-center rounded-full border border-primary/20 bg-primary/5 px-4 py-1 text-sm font-medium text-primary shadow-sm backdrop-blur transition hover:bg-primary/10 hover:border-primary/30"
            >
              Aileron
            </Link>
          </div>
          <Card className="border-slate-200 bg-white shadow-lg">
            <CardHeader>
              <CardTitle className="text-2xl font-semibold text-slate-900">{title}</CardTitle>
              {description ? <CardDescription className="text-slate-600">{description}</CardDescription> : null}
            </CardHeader>
            <CardContent>{children}</CardContent>
          </Card>
          {footer ? <div className="mt-6 text-center text-sm text-slate-600">{footer}</div> : null}
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;
