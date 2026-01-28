# CLAUDE.md — Web Frontend

Next.js 16 / React 19 / TypeScript frontend for the ColPali-Vespa visual document retrieval system. Alternative UI to the FastHTML app, sharing the same Python backend.

## Commands

```bash
npm run dev             # Dev server on port 3000
npm run build           # Production build
npm run start           # Serve production build
npm run lint            # ESLint
```

Requires Node.js >= 20.9.0 (Next.js 16 requirement). Use `nvm use 22` if available.

## Architecture

### Component Hierarchy

```
Workspace (root orchestrator)
├── Sidebar (project list, recent queries, collapsible)
├── TopBar (project context, theme toggle)
├── ScopeBar (category + document filters)
└── Content Area
    ├── Landing: QueryInput + sample queries
    └── Results: SplitView
        ├── SourcePanel → ResultCard[] (scores, blur thumbnails)
        ├── AnswerPanel (SSE-streamed AI answer with citations)
        └── DocumentViewer (modal full-page preview)
```

### Directory Layout

```
src/
├── app/
│   ├── api/              # Next.js API route handlers (proxy to backend)
│   │   ├── search/       # POST → backend search
│   │   ├── upload/       # POST → backend ingest
│   │   └── suggestions/  # GET → query autocomplete
│   ├── upload/           # Upload page
│   ├── layout.tsx        # Root layout (metadata, dark mode class)
│   ├── page.tsx          # Home → Workspace
│   └── globals.css       # Design system (CSS variables, animations)
├── components/
│   ├── document/         # DocumentViewer modal
│   ├── layout/           # Sidebar, TopBar
│   ├── results/          # SplitView, SourcePanel, ResultCard, AnswerPanel
│   ├── scope/            # ScopeBar (category/document filters)
│   ├── search/           # QueryInput (with autocomplete)
│   ├── ui/               # Primitives: Button, Badge, Input, Card, Tooltip, Skeleton
│   └── workspace.tsx     # Root component
├── hooks/
│   ├── use-search.ts     # Search state, results, SSE streaming
│   └── use-project.ts    # Projects, scope management
├── lib/
│   ├── api-client.ts     # Backend API helpers + response transforms
│   ├── store.ts          # Zustand store (theme, ranking, recent queries)
│   └── utils.ts          # formatDate, truncate, cn, pluralize
└── types/
    └── index.ts          # All TypeScript interfaces
```

### State Management

**Zustand store** (`lib/store.ts`) — persisted to localStorage under `copoly-storage`:
- `recentQueries` (max 20), `selectedProjectId`, `ranking` (`hybrid`/`colpali`/`bm25`), `isDark`

**Custom hooks** for domain logic:
- `useSearch()` — query, results, answer, streaming state, search duration
- `useProject()` / `useScope()` — project selection, category/document filters

### Backend Integration

All requests proxy through Next.js API routes to `BACKEND_URL` (default `http://localhost:7860`).

| Frontend Route | Backend Endpoint | Method | Notes |
|---|---|---|---|
| `/api/search` | `/api/search` | POST | Query + ranking |
| `/api/upload` | `/upload` | POST | FormData multipart |
| `/api/suggestions` | `/suggestions` | GET | Debounced 250ms |
| `/api/chat` (rewrite) | `/get-message` | GET | SSE stream |
| `/api/image` (rewrite) | `/api/full_image` | GET | Full-res page image |

Rewrites configured in `next.config.ts`. The `BACKEND_URL` env var controls the target.

### Data Flow — Search

```
QueryInput → useSearch.search()
  → POST /api/search → backend
  → transformResult() (normalize relevance 0-1)
  → setResults() → SourcePanel renders ResultCard[]
  → EventSource(/api/chat) → SSE messages accumulate answer text
  → AnswerPanel renders streaming response with citations
```

## Code Conventions

- **Files:** kebab-case (e.g., `query-input.tsx`, `result-card.tsx`)
- **Components:** PascalCase named exports (e.g., `QueryInput`, `ResultCard`)
- **Hooks:** `use*` prefix, one per file in `hooks/`
- **Imports:** `@/*` path alias maps to `src/*`
- **Client components:** `"use client"` directive at top of all interactive components
- **Styling:** Tailwind CSS v4 with CSS variable design tokens in `globals.css`
- **Class merging:** `cn()` utility (clsx + tailwind-merge) for conditional classes
- **Icons:** `lucide-react` exclusively
- **Animations:** CSS keyframes in `globals.css` (fadeIn, slideIn, breathe, shimmer, etc.)

### Design Tokens

Colors defined as CSS variables in `globals.css`, switching between `:root` (light) and `.dark`:
- Accent: warm coral (`#d97756` light / `#e08a6d` dark)
- Backgrounds: gray scale from `#f9fafb` (light) to `#0d0f11` (dark)
- Status colors: success (green), warning (amber), error (red), info (blue)

### Button Variants

`primary` (coral gradient), `secondary` (gray border), `ghost` (text only), `danger` (red), `accent` (coral glow). Sizes: `sm`, `md`, `lg`, `icon`.

## Environment Variables

Set in `.env.local`:

```bash
BACKEND_URL=http://localhost:7860    # Python backend URL (required)
```

## Known Gaps

These files exist but are stubs or not fully wired:
- `components/search/file-search.tsx` — not implemented
- `components/upload/upload-form.tsx` — not implemented
- `app/api/documents/route.ts` — empty placeholder
- `app/api/projects/route.ts` — empty placeholder
- Copy/thumbs up/down buttons in AnswerPanel are non-functional
- No error toast/notification system
- No pagination for large result sets
