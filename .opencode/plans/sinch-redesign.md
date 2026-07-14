# Sinch-Inspired Redesign Plan for Neurosymbolic KG Frontend

## Sinch.com Design System Analysis

### Extracted Tokens

**Colors:**
| Role | Hex | App Usage |
|------|-----|-----------|
| Primary Blue | `#1860F0` | Primary actions, selected nav, links, brand icon |
| Secondary Blue | `#2977FF` | Hover states, secondary accents |
| Blue Soft | `#EBF1FF` | Light blue backgrounds, selected item bg |
| White | `#FFFFFF` | Page/canvas background (light mode) |
| Gray 50 | `#F8F9FA` | Subtle section backgrounds, canvas bg |
| Gray 100 | `#F1F3F5` | Card backgrounds, input bg |
| Gray 200 | `#E9ECEF` | Borders, dividers |
| Gray 300 | `#DEE2E6` | Light borders, inputs |
| Gray 400 | `#ADB5BD` | Placeholder text, muted icons |
| Gray 500 | `#6C757D` | Secondary text |
| Gray 600 | `#4B575E` | Body text (Sinch's exact) |
| Gray 700 | `#343A40` | Headings in dark sections |
| Gray 900 | `#212529` | Dark section bg, headings |
| Announcement | `#D3D9DE` | Banner bar bg |
| Sand | `#F5F0EB` | Testimonial/quote bg |

**Typography:**
- Font: **Host Grotesk** (replace Inter)
- H1: 48-80px, weight 700
- H2: 28-40px, weight 700
- H3: 20-24px, weight 600
- Body: 14-16px, weight 400
- Mono: JetBrains Mono (keep for code/stats)
- Labels: 9-10px, weight 700, uppercase, tracking-wider

**Buttons (Sinch Signature):**
- Border radius: **16px** (pill shape)
- Primary: bg `#1860F0`, text white, no shadow
- Secondary: transparent bg, border `#2977FF`, text black/dark
- Hover: smooth transition, slight scale

**Cards:**
- Border radius: 12px
- Shadow: subtle (0 4px 12px rgba(0,0,0,0.08))
- Border: 1px `#E9ECEF`
- Padding: generous (p-5 to p-9)

**Layout:**
- Container-based with Bootstrap-like grid
- Alternating light/dark sections
- Very generous vertical spacing (gap-6 to gap-9)
- Rounded corners on image containers

---

## Current Frontend Architecture

- **Framework**: React 18 + TypeScript + Vite 5
- **Styling**: Tailwind CSS 3.4 (utility-first, no CSS modules)
- **Theme**: CSS custom property + Tailwind re-mapping (dark/light toggle)
- **State**: Zustand (graphStore + themeStore)
- **Icons**: lucide-react
- **Font**: Inter (body) + JetBrains Mono (code)
- **Layout**: Left nav (72px) + Canvas + Right sidebar (300-640px) + Header (h-12) + Status footer (h-6)
- **Current primary**: `blue-600 (#2563EB)`
- **Current text**: `zinc-100 (white)` in dark, inverted in light

---

## Implementation Plan

### Phase 1: Font Swap (2 files)

**File: `frontend/src/index.css`**
- Replace `@fontsource/inter/*` imports with Host Grotesk (Google Fonts via @fontsource or CDN)
- Keep `@fontsource/jetbrains-mono/*` for code
- Update `font-family` in base styles to `'Host Grotesk', ui-sans-serif, system-ui, sans-serif`

**File: `frontend/package.json`**
- Remove `@fontsource/inter`
- Add `@fontsource/host-grotesk` (if available on npm) OR add Google Fonts link to `index.html`

### Phase 2: Theme Tokens - Light Mode Default (2 files)

**File: `frontend/src/index.css`**
- Make `:root` the LIGHT theme (white/gray palette)
- Make `html.dark` the DARK theme (current zinc palette, inverted)
- New light mode CSS variables:
  ```css
  :root {
    --c-white: 255 255 255;
    --c-black: 33 37 41;       /* #212529 */
    --c-zinc-50: 248 249 250;  /* #F8F9FA - canvas bg */
    --c-zinc-100: 241 243 245; /* #F1F3F5 */
    --c-zinc-200: 233 236 239; /* #E9ECEF - borders */
    --c-zinc-300: 222 226 230; /* #DEE2E6 */
    --c-zinc-400: 173 181 189; /* #ADB5BD */
    --c-zinc-500: 108 117 125; /* #6C757D */
    --c-zinc-600: 75 87 94;    /* #4B575E - body text */
    --c-zinc-700: 52 58 64;    /* #343A40 */
    --c-zinc-800: 33 37 41;    /* #212529 */
    --c-zinc-900: 18 18 20;    /* Near black */
    --c-zinc-950: 10 10 11;    /* Near black */
    --c-chrome: 255 255 255;   /* White chrome in light mode */
  }
  ```
- Update `html, body, #root` default to light theme styles

**File: `frontend/tailwind.config.js`**
- Add Sinch-specific colors:
  ```js
  sinch: {
    blue: '#1860F0',
    'blue-light': '#2977FF',
    'blue-soft': '#EBF1FF',
    body: '#4B575E',
    heading: '#212529',
    muted: '#6C757D',
    border: '#E9ECEF',
    canvas: '#F8F9FA',
  }
  ```
- Keep existing zinc re-mapping (it now serves light mode by default)

### Phase 3: Button Radius + Primary Color (all component files)

Globally search-replace across all `.tsx` files:
- `rounded-lg` on buttons → `rounded-2xl` (16px)
- `rounded` on buttons → `rounded-2xl`
- `bg-blue-600` → `bg-[#1860F0]`
- `bg-blue-500` → `bg-[#1860F0]`
- `hover:bg-blue-500` → `hover:bg-[#2977FF]`
- `text-blue-400` → `text-[#1860F0]`
- `border-blue-500` → `border-[#1860F0]`
- `text-onaccent` → keep (still white on blue)

### Phase 4: Component-by-Component Updates

**`App.tsx` (274 lines)**
- Header: `bg-chrome/90` stays, `border-zinc-800` → `border-sinch-border`
- Graph switcher button: update border/bg for light theme
- "Run Loop" button: `rounded-2xl`, `bg-[#1860F0]`
- Status badges: update border colors
- Empty state: light theme icons and text

**`LeftNavigation.tsx` (80 lines)**
- Container: `bg-chrome` → light white
- Border: `border-zinc-800` → `border-sinch-border`
- Selected accent: update to match sinch blue
- Hover states: light bg instead of dark

**`Sidebar.tsx` (128 lines)**
- Container: `bg-chrome` → light white
- Borders: `border-zinc-800` → `border-sinch-border`
- Tab icons: update selected color to `#1860F0`
- Header: light bg, dark text

**`StatusFooter.tsx` (62 lines)**
- `bg-chrome` → light white
- `border-zinc-800` → `border-sinch-border`
- Text colors: `text-zinc-500` → `text-sinch-muted`
- Status dots: keep green/red

**`NodeInspectorCard.tsx` (98 lines)**
- `bg-zinc-900/90` → `bg-white/95` with shadow
- `border-zinc-800` → `border-sinch-border`
- Text: dark on light
- "derived" badge: keep amber styling

**`GraphCanvas.tsx` (556 lines)**
- Canvas bg: `#F8F9FA` (light gray, not pure white)
- Node fills/borders: adjust for light theme readability
- Grid lines: lighter color
- Legend: light bg, dark text

**`IngestPanel.tsx` (165 lines)**
- Header bg: light
- Input textarea: light bg, dark text, `rounded-2xl`
- Doc hint buttons: light borders, dark text
- Status badges: light theme

**`ConstructionPanel.tsx`**
- Form inputs: light bg, `rounded-2xl`
- Labels: dark text
- Buttons: sinch blue, pill radius

**`ReasoningPanel.tsx`**
- Light bg sections
- Updated border colors

**`QueryPanel.tsx`**
- Query input: light bg, `rounded-2xl`
- Results: light bg cards

**`LlmPanel.tsx`**
- Chat bubbles: light bg for assistant, blue bg for user
- Input: light bg, `rounded-2xl`

**All other panels:**
- Apply consistent light theme tokens
- Border colors: `border-sinch-border`
- Text colors: `text-sinch-body`, `text-sinch-muted`
- Button radius: `rounded-2xl`

### Phase 5: Polish

- All `rounded-lg` on buttons → `rounded-2xl`
- All `rounded` on buttons → `rounded-2xl`
- Focus rings: `focus:ring-[#1860F0]/20`
- Hover transitions: `transition-all duration-200`
- Shadows: update from dark-theme shadows to light-theme shadows
- Dark mode toggle: ensure `html.dark` class activates the zinc-based dark palette

---

## Files to Modify (in order)

1. `frontend/src/index.css` - Font imports + CSS variable redefinition
2. `frontend/tailwind.config.js` - Sinch color tokens
3. `frontend/src/App.tsx` - Header, buttons, empty state
4. `frontend/src/components/LeftNavigation.tsx` - Nav rail
5. `frontend/src/components/Sidebar.tsx` - Right sidebar
6. `frontend/src/components/StatusFooter.tsx` - Footer bar
7. `frontend/src/components/NodeInspectorCard.tsx` - Floating card
8. `frontend/src/components/GraphCanvas.tsx` - Canvas bg + node colors
9. `frontend/src/components/IngestPanel.tsx` - Ingest form
10. `frontend/src/components/ConstructionPanel.tsx` - Node/edge form
11. `frontend/src/components/ReasoningPanel.tsx` - Reasoning controls
12. `frontend/src/components/QueryPanel.tsx` - Query input
13. `frontend/src/components/LlmPanel.tsx` - Chat interface
14. `frontend/src/components/AgentPanel.tsx` - Agent interface
15. `frontend/src/components/OntologyPanel.tsx` - Ontology viewer
16. `frontend/src/components/GraphsPopover.tsx` - Popover
17. `frontend/src/components/HistoryPopover.tsx` - Popover
18. `frontend/src/components/ConnectionCenter.tsx` - Modal
19. `frontend/src/components/GraphMaintenancePanel.tsx` - Panel
20. `frontend/src/components/TripleStorePanel.tsx` - Panel
21. `frontend/src/components/SkillManager.tsx` - Panel
22. `frontend/src/components/MemoryInspector.tsx` - Panel
23. `frontend/src/components/pages/DocumentsPage.tsx` - Page
24. `frontend/src/components/pages/LogicPage.tsx` - Page
25. `frontend/src/components/pages/InferencePage.tsx` - Page
26. `frontend/src/components/pages/QueryPage.tsx` - Page
27. `frontend/src/components/panels/BuildPanel.tsx` - Panel
28. `frontend/src/components/panels/QueryExplorePanel.tsx` - Panel
29. `frontend/src/components/panels/AssistantPanel.tsx` - Panel
30. `frontend/src/components/panels/ToolsPanel.tsx` - Panel

---

## Verification

After implementation:
1. `cd frontend && npm run dev` - Visual check of all pages
2. Toggle dark/light mode - both should work
3. Check all 5 nav pages (Canvas, Documents, Logic, Inference, Query)
4. Check sidebar tabs (Build, Reason, Query, Assistant, Tools)
5. Verify button pill-radius (16px) on all CTAs
6. Verify Host Grotesk font loads correctly
7. `npm run build` - No TypeScript/build errors
