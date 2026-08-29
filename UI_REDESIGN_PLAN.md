# UI Redesign Plan: Standard Chat Interface

## Current Issues
1. **Settings panel is inline** - expands below header, takes 40% of screen
2. **Provider/model/API key selection buried** in settings panel
3. **No persona selector** in main UI (only system prompt textarea)
4. **Session sidebar shows provider/model badges** - clutter
4. **File upload inline** in input area - not standard
5. **Voice buttons inline** with input - not standard
6. **No global vs session settings separation**

## Target: Standard Chat UI (ChatGPT/Claude pattern)

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│  Top Bar:  [Logo] [Session Title]          [Model▼] [⚙]    │
├──────────────────┬──────────────────────────────────────────┤
│                  │                                          │
│  Session List    │            Chat Area                     │
│  (Collapsible)   │                                          │
│                  │  ┌────────────────────────────────────┐  │
│  [+ New Chat]    │  │ Message 1 (user)                   │  │
│                  │  │ Message 2 (assistant)              │  │
│  Session 1       │  │ Message 3 (user)                   │  │
│  Session 2       │  │ ...                                │  │
│  Session 3       │  │                                    │  │
│                  │  └────────────────────────────────────┘  │
│                  │  ┌────────────────────────────────────┐  │
│                  │  │ [📎] [🎤]  Type message...     [▶] │  │
│                  │  └────────────────────────────────────┘  │
└──────────────────┴──────────────────────────────────────────┘
```

### Components to Build/Modify

#### 1. **TopBar** (New Component)
- Left: Logo + Session title (clickable to rename)
- Center: **Model Selector Dropdown** (provider + model in one)
- Right: **Persona Selector Dropdown** + Settings (gear icon → modal)

#### 2. **ModelSelectorDropdown** (New Component)
- Single dropdown: "OpenRouter ▼" → shows provider groups with models
- Shows current selection: "OpenRouter / Claude 3.5 Sonnet"
- Quick switch without opening settings modal

#### 3. **PersonaSelectorDropdown** (New Component)
- Dropdown: "Default (JARVIS) ▼" → list of saved personas + "Custom..."
- "Custom" opens inline system prompt editor (small, not full panel)
- Shows preview of active persona

#### 4. **SettingsModal** (New Component - replaces inline panel)
- **Tabs**: General | Providers | Personas | Advanced
- **General**: Default provider, default model, default persona
- **Providers**: API keys per provider (saved to global defaults)
- **Personas**: CRUD for personas (name, description, system_prompt)
- **Advanced**: Base URLs, debug options

#### 5. **SessionSidebar** (Refactor)
- Clean session list: Title + updated time only
- No provider/model badges
- Collapsible with hamburger menu
- Hover actions: Rename, Delete
- "New Chat" at top

#### 6. **ChatArea** (Refactor ChatCanvas)
- Remove inline settings panel
- Remove provider badge from header
- Standard message bubbles
- Input bar: attachment | voice | text | send

#### 7. **InputBar** (Refactor)
- Left: Attachment (📎), Voice (🎤)
- Center: Textarea (auto-grow)
- Right: Send button
- File preview as floating chip above input (not inline block)

## Implementation Order

### Phase 1: Core Layout (New Components)
1. Create `TopBar.tsx` with model/persona dropdowns + settings trigger
2. Create `ModelSelectorDropdown.tsx`
3. Create `PersonaSelectorDropdown.tsx` (fetch from `/api/personas`)
4. Create `SettingsModal.tsx` with tabs
5. Refactor `ChatCanvas.tsx` to use new layout
6. Refactor `SessionSidebar.tsx` to clean version

### Phase 2: Settings Modal Functionality
7. Wire SettingsModal tabs to API:
   - GET/POST `/api/defaults` (global defaults)
   - GET/POST/PATCH/DELETE `/api/personas`
   - GET/POST `/api/settings` (provider API keys)

### Phase 3: Polish
8. Keyboard shortcuts (⌘+K for command palette, ⌘+N new chat)
9. Mobile responsive (sidebar drawer, bottom sheet for settings)
10. Dark/light theme toggle in settings
11. Streaming responses (if backend supports)

## API Endpoints Needed (Already Exist)
- `GET /api/defaults` - global defaults
- `PATCH /api/defaults` - update global defaults
- `GET /api/personas` - list personas
- `POST /api/personas` - create persona
- `PATCH /api/personas/:id` - update persona
- `DELETE /api/personas/:id` - delete persona
- `GET /api/settings` - get provider API keys
- `POST /api/settings` - save provider API keys
- `GET /api/sessions` - list sessions
- `POST /api/sessions` - create session
- `PATCH /api/sessions/:id` - update session (title, provider, model, system_prompt)
- `DELETE /api/sessions/:id` - delete session
- `GET /api/sessions/:id/conversations` - load messages
- `POST /api/chat` - send message

## Data Flow

### Global Settings (persisted once)
```
User opens SettingsModal → Providers tab
→ Enters OpenRouter API key
→ POST /api/settings {key: "openrouter_api_key", value: "sk-..."}
→ Stored in user_settings table
→ Applied to ALL new sessions automatically
```

### Session Settings (per-session override)
```
User selects model in TopBar dropdown
→ Updates session via PATCH /api/sessions/:id {provider, model}
→ This session uses these values
→ New sessions still use global defaults
```

### Personas
```
User creates persona in SettingsModal → Personas tab
→ POST /api/personas {name: "JARVIS", system_prompt: "..."}
→ Selects persona in PersonaSelectorDropdown
→ PATCH /api/sessions/:id {system_prompt: "..."} (or uses global default)
```

## Files to Create
- `frontend/src/components/TopBar.tsx`
- `frontend/src/components/ModelSelectorDropdown.tsx`
- `frontend/src/components/PersonaSelectorDropdown.tsx`
- `frontend/src/components/SettingsModal.tsx`
- `frontend/src/hooks/usePersonas.ts` (fetch/create personas)
- `frontend/src/hooks/useGlobalSettings.ts` (defaults + provider keys)

## Files to Modify
- `frontend/src/components/ChatCanvas.tsx` - complete rewrite using new layout
- `frontend/src/components/SessionSidebar.tsx` - simplify, remove badges
- `frontend/src/app/page.tsx` - update to use new ChatCanvas
- `frontend/src/components/ProviderSelector.tsx` - keep for SettingsModal Providers tab

## Acceptance Criteria
- [ ] Chat UI looks like ChatGPT/Claude (sidebar + chat area + top bar)
- [ ] Model selector in top bar (one-click switch)
- [ ] Persona selector in top bar (one-click switch)
- [ ] Settings in modal, not inline panel
- [ ] Global API keys saved once, applied to all sessions
- [ ] Personas CRUD in settings modal
- [ ] Session sidebar clean (title + time only)
- [ ] File upload as floating chip
- [ ] Voice input as mic button in input bar
- [ ] All existing functionality preserved
- [ ] TypeScript builds, tests pass
