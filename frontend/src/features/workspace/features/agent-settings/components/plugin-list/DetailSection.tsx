import React from 'react';

export const DetailSection: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
  <section>
    <h3 className="mb-2 text-sm font-medium">{title}</h3>
    {children}
  </section>
);
