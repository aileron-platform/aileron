"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { resolveLocale, translations } from "./i18n";

function DefaultPageContent() {
  const searchParams = useSearchParams();
  const t = translations[resolveLocale(searchParams.get("lang"))];

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md px-6">
        <div className="mb-6">
          <svg
            className="mx-auto h-16 w-16 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-semibold text-gray-700 mb-4">
          {t.title}
        </h1>
        <p className="text-gray-500 mb-6">
          {t.descBefore}{" "}
          <code className="bg-gray-200 px-1 rounded">/workspace</code>{" "}
          {t.descAfter}
        </p>
        <div className="bg-gray-100 rounded-lg p-4 text-left text-sm text-gray-600">
          <p className="font-medium mb-2">{t.quickStart}</p>
          <code className="block bg-gray-200 px-3 py-2 rounded text-xs">
            npx create-next-app@latest /workspace --typescript --tailwind
          </code>
        </div>
      </div>
    </div>
  );
}

export default function DefaultPage() {
  return (
    <Suspense>
      <DefaultPageContent />
    </Suspense>
  );
}
