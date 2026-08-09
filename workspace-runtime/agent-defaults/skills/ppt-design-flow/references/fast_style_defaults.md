# Fast Style Defaults

Fast mode uses exactly one defaults bucket. The bucket guides `design_spec.md`; it does not replace the user's explicit brand, school, company, lab, course, or product identity.

## Decision algorithm

1. If intake captured explicit brand identity, apply that identity verbatim first: colour, typography, logo placement, and domain symbols override the bucket defaults.
2. Else map `用途` to a bucket:
   - `答辯 / 學術` → `沉穩學術`
   - `募資 / pitch` → `明亮專業`
   - `產品介紹` → `現代潔淨`
   - `內訓 / 教學` → `親和清晰`
3. If no clear brand identity or 用途 mapping exists, use fallback `明亮專業`.

## 沉穩學術

- Colour palette: primary `#17324D`, accent `#8BA4C8`, background `#F5F7FA`, text `#172033`.
- Font stack: heading `"Noto Serif TC", "Source Han Serif TC", "PMingLiU", serif`; body `"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif`.
- Layout preference: cover with institution/title hierarchy; ToC as numbered agenda with restrained dividers; content page grid is text-forward with evidence blocks and figure captions.
- Representative use cases: thesis defence, academic research briefing.

## 明亮專業

- Colour palette: primary `#2563EB`, accent `#14B8A6`, background `#FFFFFF`, text `#111827`.
- Font stack: heading `"Inter", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif`; body `"Inter", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif`.
- Layout preference: cover with large claim and clear proof point; ToC as compact progress cards; content page grid balances headline, metric, and visual at roughly 50/50.
- Representative use cases: fundraising pitch, executive proposal.

## 現代潔淨

- Colour palette: primary `#0F766E`, accent `#F59E0B`, background `#F8FAFC`, text `#0F172A`.
- Font stack: heading `"Inter", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif`; body `"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", Arial, sans-serif`.
- Layout preference: cover with product object or workflow as first signal; ToC as simple section rail; content page grid uses generous whitespace, weak borders, and 60/40 image-to-text balance.
- Representative use cases: product introduction, feature roadmap.

## 親和清晰

- Colour palette: primary `#7C3AED`, accent `#F97316`, background `#FFFBF5`, text `#1F2937`.
- Font stack: heading `"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif`; body `"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", Arial, sans-serif`.
- Layout preference: cover with approachable title and concrete outcome; ToC as learning path; content page grid uses large headings, icon-led chunks, examples, and high-contrast callouts.
- Representative use cases: internal training, teaching deck.
