# Mobile UX Overhaul Plan

Status: **done** — planned 2026-07-14, all three phases implemented. Implemented phase by phase; each phase was independently shippable.

## Context

Using the Chatbot from a phone browser is bad in two ways:

1. **The message textarea is tiny** — the composer squeezes four fixed-width controls
   (📎 42px, 🌐 42px, textarea, Send ~72px) onto one row; on a ~360px phone the
   textarea gets ~150px of width. The planned 🧩 toggle (APP_TOOLS_PLAN) would make
   it worse.
2. **The UI "moves around" and is never truly full-screen** — the root layout uses
   `height: 100vh` (`App.tsx`, `AuthPage.tsx`), which on mobile includes the URL-bar
   area, so the composer sits under browser chrome and gets shoved by the soft
   keyboard. There is no `dvh`, no `viewport-fit`, no safe-area handling, and no
   keyboard handling beyond the `outerWidth` workaround in `App.tsx`.

**Decision: fix in place, no rewrite.** The frontend is 7 small components with the
freshly-done paper×Claude theme; both problems have localized, well-known fixes.
A rewrite (Tailwind / component lib) would churn the theme and every e2e selector
for no user-visible gain.

**Decisions taken:**
- Composer moves to a unified **pill layout everywhere** (not mobile-only) — one
  code path, and it's the same pattern Claude/ChatGPT use on desktop.
- **PWA deferred** — the app is served over plain LAN HTTP, so Android won't
  install it as a real standalone app until TLS exists; revisit then.

**Responsive-styling strategy:** the app uses inline styles + CSS vars, and media
queries can't be inline. Add a *small* set of classes to `frontend/src/index.css`
for the genuinely responsive pieces (`app-shell`, `top-bar`, `composer`,
`chat-thread`, `.bubble` width); keep the JS `mobile` flag only for structural
differences (sidebar drawer, hiding the username). Media queries use `640px` to
match `MOBILE_BREAKPOINT`. UI text stays English.

---

## Phase 1 — Viewport / full-screen foundation

- [x] **`frontend/index.html`** — viewport meta becomes:
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, interactive-widget=resizes-content" />
  ```
  `interactive-widget=resizes-content` (Chrome/Android ≥108, ignored elsewhere)
  makes the keyboard shrink the layout so the composer sits above it — no JS
  needed. `viewport-fit=cover` enables `env(safe-area-inset-*)`.

- [x] **`frontend/src/index.css`** — add:
  ```css
  .app-shell { height: 100vh; height: 100dvh; }   /* dvh tracks URL-bar collapse; vh fallback */
  html, body { overflow: hidden; overscroll-behavior: none; }  /* app owns all scrolling */
  .top-bar { padding-top: env(safe-area-inset-top); }
  .composer { padding: 12px 24px; padding-bottom: max(20px, env(safe-area-inset-bottom)); }
  .chat-thread { padding: 16px 24px; overscroll-behavior: contain; }
  @media (max-width: 640px) {
    .composer { padding: 8px 10px; padding-bottom: max(10px, env(safe-area-inset-bottom)); }
    .chat-thread { padding: 12px 10px; }
  }
  ```
  A class (not inline `100dvh`) because an inline style object has a single
  `height` key — no cascade fallback for browsers without `dvh`.

- [x] **`frontend/src/App.tsx`** — root div: drop inline `height: "100vh"`, add
  `className="app-shell"`. Top bar div: add `className="top-bar"`, change
  `height: 48` → `minHeight: 48` (safe-area padding is 0 in a normal tab, so
  nothing changes there).

- [x] **`frontend/src/components/AuthPage.tsx`** — wrapper: `100vh` →
  `className="app-shell"`. Set username/password input `fontSize: 16` —
  **iOS Safari auto-zooms on focusing any input with font-size < 16px**, a major
  "UI moves and never recovers" cause.

Deliberately **not** adding a `VisualViewport` JS hook now — Android doesn't need
it with `interactive-widget`; add later only if iOS testing shows the composer
occluded by the keyboard.

## Phase 2 — Composer pill redesign

**`frontend/src/components/MessageInput.tsx`** — unified layout, all screen sizes.
The outer wrapper keeps its flex-column + pending-chips row and gets
`className="composer"` (padding moves to CSS, Phase 1). New input area:

```
<div style={pill}>                      // border 1px var(--border), borderRadius 16,
                                        // background var(--surface), padding ~8-10
  <textarea rows={1} ... />             // full-width, border:none, background:transparent,
                                        // outline:none, fontSize 16, auto-grow
  <div style={{display:"flex", alignItems:"center", gap:4}}>
    📎 aria-label="Attach files"        // 32×32 borderless icon btn, radius 8, hover surface-hover
    🌐 aria-label="Toggle web access"   // same; keeps aria-pressed + accent-soft/accent when on
    <div style={{flex:1}} />
    Send / ■ Stop                       // right-aligned, height 34, padding 6px 14px,
  </div>                                // keep visible text (e2e names) + accent/danger colors
</div>
```

- [x] **Auto-grow textarea** (stays uncontrolled): `rows={1}`, `onInput`:
  `el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 160) + "px"`,
  `overflowY: "auto"` past the ~6-line cap. In `submit()`, after clearing the
  value, reset `ref.current.style.height = "auto"`.
- [x] **fontSize 16** on the textarea (was 14) — prevents iOS focus-zoom.
- [x] **Placeholder** shortened to `"Type a message…"` (the long suffix overflowed
  on phones; the e2e regex `/Type a message/` still matches). Keep Enter=send /
  Shift+Enter=newline `onKeyDown` as-is.
- [x] Keep the hidden `<input type="file" multiple hidden>` exactly as-is (e2e
  `setInputFiles` depends on it) and all existing aria-labels/titles.

Result on a 360px phone: textarea width goes from ~150px to ~330px; a future 🧩
toggle costs nothing.

## Phase 3 — Top bar, bubbles, thread

- [x] **`App.tsx`** — render the username span in the top bar only when `!mobile`
  (Logout stays; it's small, and dropping the username frees enough room).
- [x] **`frontend/src/components/ChatThread.tsx`** — bubbles: remove inline
  `maxWidth: "72%"`; add to `index.css`:
  ```css
  .bubble { max-width: 72%; }
  @media (max-width: 640px) { .bubble { max-width: 88%; } }
  ```
  Keep the state-dependent `minWidth: editing ? "60%" : undefined` inline.
- [x] **`ChatThread.tsx`** — scroll container: drop inline `padding: "16px 24px"`,
  add `className="chat-thread"` (CSS in Phase 1).
- [x] Note the CSS-classes-for-responsive exception in `CLAUDE.md`'s frontend
  section (one line).

## Out of scope (deliberate)

- **PWA/manifest** — inert over plain LAN HTTP on Android; revisit when the
  mini-PC gets TLS.
- **VisualViewport keyboard hook** — only if iOS manual testing shows the
  composer hidden behind the keyboard.
- **`outerWidth` → `matchMedia` refactor** of mobile detection — the current
  workaround still works; not worth the risk in this pass.

## Verification (per phase, full sweep at the end)

1. `cd frontend && npm run lint && npm run build`; `make unit-frontend`.
2. **Manual phone test** (Vite binds 0.0.0.0): `make backend` + `make frontend`,
   open `http://<laptop-LAN-IP>:5174` on the phone. Checklist:
   - no page-level pan when the keyboard opens/closes;
   - composer visible above the keyboard while typing;
   - no zoom on textarea/auth-input focus;
   - no dead strip after the URL bar collapses;
   - sidebar drawer + backdrop still work;
   - textarea auto-grows, caps at ~6 lines, resets after send;
   - rotation portrait↔landscape; desktop still looks right.
3. `make e2e` — expected all green with **no selector changes** (placeholder
   regex, `Send`/`■ Stop` names, `Toggle web access`, `input[type="file"]`,
   `.bubble-*` are all preserved). Per project convention, any e2e fixes happen
   as the final pass.
