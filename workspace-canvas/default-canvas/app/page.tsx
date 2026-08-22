"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { resolveLocale, translations } from "./i18n";

function DefaultPageContent() {
  const searchParams = useSearchParams();
  const locale = resolveLocale(searchParams.get("lang"));
  const t = translations[locale];

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  useEffect(() => {
    type CanvasTheme = "light" | "dark";
    type AileronWindow = Window & { aileron?: { theme?: CanvasTheme } };
    const applyTheme = (theme: CanvasTheme) => {
      const isDark = theme === "dark";
      document.documentElement.classList.toggle("dark", isDark);
      document.body.classList.toggle("dark", isDark);
      document.documentElement.dataset.theme = theme;
      document.documentElement.style.colorScheme = theme;
    };
    const handleThemeChange = (event: Event) => {
      const theme = (event as CustomEvent<{ theme?: CanvasTheme }>).detail?.theme;
      if (theme) applyTheme(theme);
    };
    const currentTheme = (window as AileronWindow).aileron?.theme;
    if (currentTheme) applyTheme(currentTheme);
    window.addEventListener("aileron:themechange", handleThemeChange);
    return () => window.removeEventListener("aileron:themechange", handleThemeChange);
  }, []);

  return (
    <main className="canvas-shell">
      <div className="canvas-grid" aria-hidden="true" />
      <div className="canvas-orbit canvas-orbit-one" aria-hidden="true" />
      <div className="canvas-orbit canvas-orbit-two" aria-hidden="true" />

      <section className="canvas-board" aria-labelledby="canvas-title">
        <header className="canvas-hero">
          <div>
            <p className="canvas-eyebrow">{t.eyebrow}</p>
            <h1 id="canvas-title">{t.title}</h1>
            <p className="canvas-description">{t.description}</p>
          </div>
          <div className="canvas-status">
            <span aria-hidden="true" />
            {t.status}
          </div>
        </header>

        <div className="canvas-workbench">
          <ol className="canvas-steps">
            <li>
              <span className="step-index">01</span>
              <div>
                <h2>{t.outcomeLabel}</h2>
                <p>{t.outcomeDescription}</p>
              </div>
            </li>
            <li>
              <span className="step-index">02</span>
              <div>
                <h2>{t.contentLabel}</h2>
                <p>{t.contentDescription}</p>
              </div>
            </li>
            <li>
              <span className="step-index">03</span>
              <div>
                <h2>{t.syncLabel}</h2>
                <p>{t.syncDescription}</p>
              </div>
            </li>
          </ol>

          <aside className="canvas-specimen" aria-label={t.promptLabel}>
            <div className="specimen-header">
              <span>{t.promptLabel}</span>
              <span>{t.promptType}</span>
            </div>
            <blockquote>{t.promptExample}</blockquote>
          </aside>
        </div>

        <footer className="canvas-footer">
          <span className="footer-mark" aria-hidden="true">A</span>
          <p>{t.footer}</p>
          <span className="footer-coordinate" aria-hidden="true">00° / 00°</span>
        </footer>
      </section>
    </main>
  );
}

export default function DefaultPage() {
  return (
    <Suspense>
      <DefaultPageContent />
    </Suspense>
  );
}
