# Roadmap — embedded-engineer features

Status legend: ✅ done · 🚧 in progress · ⬜ planned

## Infrastructure
- ✅ **Page manifest** (`assets/pages.js` → `window.DSW_PAGES`): every page's number,
  image, owning section, and searchable text. Underpins the reference/bookmark
  features and page-level search. Plus `window.DSW_ID` to namespace per-datasheet
  local storage.

## Personal reference & bookmarks (client-side, localStorage)
- ✅ **Star pages**: a star toggle on every source-page thumbnail and in the
  lightbox; state persisted per datasheet.
- ✅ **Personal Reference page** (`starred.html`): a thumbnail gallery of the
  starred pages, with a slider to set thumbnail size. Print / clear / open.
- ✅ **Reference generator** (`reference.html`): build a thumbnail gallery from a
  comma-separated list of page numbers/ranges (e.g. `1, 3, 5-8`). Below the input,
  a **search bar** finds page numbers by keyword (page-level full-text) so the
  user can add them. Shareable via URL hash; adjustable thumbnail size; "star all".

## Register-centric
- ✅ **Register map index** (`registers.html`): every detected register across the
  datasheet (name, address, fields) linked to its section — like the code index.
- ✅ **Interactive bit-field calculator**: on each register table, enter field
  values → live hex/binary register value, and decode a pasted hex value back.
- ✅ **Export to C header / CMSIS-SVD** from detected registers.
- ⬜ **Import an existing SVD** for authoritative register data.

## Search & navigation
- ✅ **Ctrl-K command palette** (jump to section/register/pin).
- ⬜ **Ask-the-datasheet Q&A (RAG)** using the medium/large tier's local embeddings.
- ⬜ **Acronym/glossary tooltips**.

## Practical / quality-of-life
- ⬜ **Per-peripheral init-code generator** (LLM tiers).
- ✅ **Personal notes / highlights** (localStorage).
- ⬜ **Electrical-characteristics tables** as sortable/filterable HTML.
- ⬜ **Single-file / PWA offline export** + print stylesheet.

## Trust
- ⬜ **Provenance + confidence badges** (heuristic vs LLM) on every datum.
