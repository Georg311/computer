## [0.9.21.29] - 2026-11-02

### Fixed
- 🐛 **OpenAI Chat Completions Usage-Events enthielten keine Cache-Daten.** `stream_openai_completions()` extrahierte nur `prompt_tokens`, `completion_tokens`, `total_tokens` aus dem Usage-Chunk und warf `cache_read_input_tokens` + `prompt_token_details` weg. Jetzt: beide Felder werden mitgegeben, sodass `effective_tokens` korrekt `input - cache_read` berechnet.

## [0.9.21.28] - 2026-11-02

### Fixed
- 🐛 **TokenEconomizer `effective_tokens` zeigte weighted cost statt fresh input.** `/api/chats/te/status` Endpoint ignorierte die `TeStatus` DB row komplett und berechnete alles neu aus Messages. Jetzt: DB-Primary (liest `te_status` direkt), Message-Fallback (berechnet live wenn keine row existiert). `effective_tokens` = `sum(input - cache_read)` pro Turn — zeigt echte uncached prompt size. `session_cost_usd` bleibt weighted für billing-Genauigkeit. Backfix: `backfill_te.py` berechnet jetzt auch fresh input tokens statt weighted cost.

## [0.9.21.27] - 2026-11-02

### Fixed
- 🐛 **TokenEconomizer `record_tool_call()` never wrote to DB.** `get_session_factory()` returned an async_sessionmaker, not a session — calling `.execute()` on it raised AttributeError silently, so tool_usage and te_status stayed empty. Rewrote all DB access to use `async with get_session_factory()() as session:` (correct async context manager pattern). Also fixed `TeStatus.get_by_chat()` and `TeStatus.ensure()` in models/te.py and `get_session_costs()` in cost_tracker.py to use the same pattern.

## [0.9.21.26] - 2026-11-02

### Fixed
- 🐛 **TokenEconomizer empty values when no te_status row exists.** The `/api/chats/te/status` endpoint returned hardcoded zeros when no `TeStatus` DB row existed (which is the case before any tool call has been recorded). Now falls back to in-memory cache via `get_session_costs()` even when no DB row exists, so cached token data from previous sessions is displayed.

## [0.9.21.25] - 2026-11-01

### Fixed
- 🐛 **TokenEconomizer frontend display.** Frontend bundle was not rebuilt after TE feature addition — `TeStatusPanel.svelte` and related UI code were missing from the production JS chunks. Rebuilt frontend and deployed to main so `/te-status` panel renders correctly in the UI.

## [0.9.21.24] - 2026-11-01

### Fixed
- 🐛 **TokenEconomizer `TeStatus.get_by_chat()` query.** Method was a `@staticmethod` referencing undefined `cls`, and used `session.get(cls, chat_id)` which does a PK lookup instead of filtering by the `chat_id` FK. Changed to `@classmethod` with proper `sa_select(cls).where(cls.chat_id == chat_id)` query — now returns the correct row so TE status data is persisted and readable.

## [0.9.21.23] - 2026-11-01

### Fixed
- 🐛 **TokenEconomizer cache data extraction.** `get_session_estimate()` and `calculate_cost()` were reading `cache_read_input_tokens` / `cache_creation_input_tokens` fields that don't exist in cptr's usage records. Data is stored as `input_tokens_details.cached_tokens`. Added `_extract_cache_tokens()` helper that handles both the standard field names and cptr's nested layout, so cache-aware token accounting now works correctly with real data. Also increased `session_cost_usd` rounding precision from 2 to 8 decimal places (values under $0.01 were being rounded to 0).

## [0.9.21.21] - 2026-11-01

### Fixed
- 🐛 **TokenEconomizer empty values fix.** `effective_tokens`, `total_tokens`, `cache_savings_pct`, `pricing_overhead` and `session_cost_usd` were always 0 because (a) `record_tool_call()` never wrote DB values — only created empty rows; (b) the `/api/chats/te/status` endpoint read only from DB, ignoring the in-memory cache where actual data lived. Fixed by: syncing DB `te_status` row with computed values on every tool call; adding `get_session_costs()` fallback in the endpoint so cached values fill in when DB is still 0 (handles restarts and pre-migration chats). Also fixed `get_session_estimate()` formula — `effective_tokens` is now fresh input tokens (`input - cache_read`) instead of weighted cost, `cache_savings_pct` correctly shows % of input served from cache, `session_cost_usd` rounded to 2 decimal places.

### Added
- 🔍 **`search_files` — `filepaths_only` parameter.** Returns relative file paths (e.g. `cptr/utils/ai.py`) instead of matching lines, for use-cases that only need file discovery.
- 💰 **TE Pricing admin settings.** Full CRUD for custom model pricing (`/api/admin/te/pricing`) with a new Settings tab, grouped by provider, showing defaults, overrides, and merged values. Add/delete custom models supported.

### Fixed
- 🐛 **Admin pricing UI fixes.** Null-checked `groupByProvider` to prevent `'can't convert undefined to object'`, moved Svelte template reduce logic out of the template, removed duplicate TE Pricing routes from `admin.py`, removed redundant data transform (backend already returns `{defaults, custom, merged}`), adapted `getTePricing` to actual `{models, overrides}` API response format, switched pricing tab to 'dollar' icon (Iconoir SVG).
- 🐛 **`search_files` — `filepaths_only` path extraction.** Corrected path extraction logic for relative paths so deduplicated file paths are properly returned.
- 🐛 **TE UI fixes.** Removed `hasChatContent` guard that disabled TE UI buttons, added header button and plus menu entry, fixed missing `commandTeConfig` key, improved padding/spacing, added missing `teConfig` translations to all locales, fixed HTML escaping in TE status messages, fixed Svelte `$props()` destructuring for `onteStatus`.
- 🐛 **Frontend:** Load fonts locally instead of from Google Fonts.

### Docs
- 📝 **Clarify `filenames_only` vs `filepaths_only`.** Updated docstrings to clearly distinguish bare filenames (`ai.py`) from relative file paths (`cptr/utils/ai.py`).

## [0.9.21.20] - 2026-11-01

### Fixed
- 🐛 **TokenEconomizer test fixes.** Fixed `command_not_found` regex (end-of-string anchor + optional group), fixed `module_not_found` regex (`can't` vs `cannot`). Made `record_fact_fire()` async for proper await in tests. Fixed mock commit as async in `test_updates_fire_status`. Fixed `test_loop_guard.py` config_overrides nesting + envelope param. Fixed `test_pricing_wrapper.py` floating-point tolerance + total_tokens. Fixed `test_cost_tracker.py` async mock patterns. Fixed `test_tool_usage_tracker.py` async context manager mocks. Added `pytest.ini` with `asyncio_mode=auto`. All 108 tests now passing.
- 🐛 **Fix `get_active_facts()` await in chat_task.py.** The function is async but was called sync at 3 call sites (lines 1958, 2324, 2641), causing `TypeError: 'coroutine' object is not iterable`. Now properly awaited at all locations.

## [0.9.21.18] - 2026-10-31

### Added
- 🧪 **TokenEconomizer integration (Phase 0).** Copied TE reference implementation to `cptr/utils/te/` (pricing, config, loopguard, microskills, toolprune, trace modules). Added SQLAlchemy models (`TeStatus`, `ToolUsage`, `RepoFacts`, `LoopEnvelope`) and Alembic migration for new DB tables.
- 🧪 **TokenEconomizer integration (Phase 3).** Frontend TE Skills Panel — Svelte component in Burger menu displaying learned repository facts with fire status (🗝️/💡) and confirmation counts. Slash command `/te-skills` opens the panel. Fixed missing `onteSkills` prop chain (`ChatInput` → `ChatPanel`).

## [0.9.21.19] - 2026-11-01

### Added
- 🧪 **TokenEconomizer integration (Phase 1).** Pricing/Cost Monitoring — `pricing_wrapper.py` mit absoluten Dollar-Preisen pro Model, `cost_tracker.py` für Session-Tracking in SQLite, `/api/chats/te/status` Endpoint, Frontend TE Status Panel im Burger Menü. Slash command `/te-status` öffnet Panel.
- 🧪 **TokenEconomizer integration (Phase 2).** Tool Pruning Vorschläge — Hybrid-Ansatz: `analyze_tool_pruning()` erkennt nie genutzte oder über X Sessions ungenutzte Tools, `/api/chats/te/toolpruning/apply/{chat_id}` Endpoint, Frontend TE Tools Panel mit Apply-Buttons. Slash command `/te-tools` öffnet Panel.
- 🧪 **TokenEconomizer integration (Phase 4).** Loop Guard — Turn-level failure-loop intervention: `loop_guard.py` mit DB-persistiertem State, 2-Tier-Cascade (Tier-0 rule-based + optional Tier-1 LLM Judge), Nudge als Toast-Nachricht, Abort-Vorschlag als Banner mit manueller Bestätigung (kein Auto-Stop!). Svelte Components `LoopNudgeToast.svelte` und `LoopAbortBanner.svelte` in `ChatPanel.svelte` integriert. Socket.IO Events (`loop_nudge`, `loop_abort_request`, `loop_guard_status`) broadcasten via `socket/main.py`.
- 🧪 **TokenEconomizer integration (Phase 5).** Config Management — `/api/chats/te/config` + `/api/chats/te/config/update` Endpoints zum Lesen/Schreiben von TE Config in config.toml. Frontend TE Config Panel (`TEConfigPanel.svelte`) mit Core Toggles (microskills, toolpruning, loopguard) und Advanced Expandable Section (max_facts, max_tokens, thresholds). Admin Settings Integration: `/api/admin/te/pricing` CRUD endpoints zum Verwalten von Model-Preisen.

## [0.9.21.17] - 2026-10-27

### Fixed
- 🐛 **Workspace data corruption prevention.** Added `_safe_workspace_data()` to sanitize workspace data on write. Prevents corruption where `workspace.data` becomes an integer (0) or malformed string by ensuring only valid dicts are stored. Handles existing corruption by parsing JSON strings or defaulting to `{}`.
## [0.9.21.16] - 2026-10-27

### Fixed
- 🐛 **Workspace data deserialization.** Fixed `ValueError` caused by corrupted `workspace.data` values (integers or malformed JSON strings). The `get_workspace` endpoint now safely handles string/integer data types via explicit JSON parsing with fallback to `{}`.
## [0.9.21.15] - 2026-10-24

### Fixed
- 🎨 **Send button styling.** Darker blue gradient (blue-600 → indigo-800) for FAB and chat send buttons. Fixed chat button to use fixed `h-12 w-12` size so it doesn't change between states. Reduced send arrow icon to 20px for better visual balance.

## [0.9.21.14] - 2026-10-20

### Fixed
- 🐛 **Telegram image forwarding.** Bridge `_send_final_files` is now always called after the final text edit, ensuring generated images and displayed files are sent to Telegram chats. Previously, short responses caused an early return before files were forwarded.

## [0.9.21.13] - 2026-10-20

### Added
- 📎 **Telegram file forwarding.** Bridge `_send_final_files` scans task output items for file entries (images, documents) and sends them as Telegram photos/documents via `send_photo`/`send_document`. Deduplicates by path.
- 🖼️ **Telegram image & document forwarding.** Images generated via `image_generate` are now sent to Telegram chats as photos. Files displayed via `display_file` (images, PDFs, documents) are forwarded as photos or documents. Artifacts from `create_artifact` are sent as documents. MIME types are correctly detected from file extensions.

## [0.9.21.12] - 2026-10-20

### Added
- 📎 **Telegram file forwarding.** Bridge `_send_final_files` scans task output items for file entries (images, documents) and sends them as Telegram photos/documents via `send_photo`/`send_document`. Deduplicates by path.

## [0.9.21.11] - 2026-10-17

### Changed
- 🔖 **Version bump.** Bumped version to 0.9.21.11.

## [0.9.21.9] - 2026-10-16

### Added
- ⏱️ **get_current_time.** Enhanced to return rich temporal context in structured JSON format.
- 📁 **Directory Watcher.** New `watch_directory` tool to monitor directories for file changes. Supports both Notification Mode (system message) and Trigger Mode (auto-trigger new agent turn on pattern match).

### Fixed
- 🔧 **inotify support.** Added ctypes fallback for `inotify_init`/`inotify_add_watch`/`inotify_rm_watch` when Python 3.13 lacks `os.inotify_*` bindings.
- 🐛 **Race condition.** Centralized inotify event polling in the manager to prevent multiple watchers from competing for the same global fd.

## [0.9.21.7] - 2026-10-16

### Fixed
- 📱 **Mobile UX.** Resolved FAB race conditions and build errors.
- 🛠️ **Alembic Migrations.** Fixed workspace ID autoincrement issues.

### Docs
- 📝 **Mobile UX Plan.** Updated documentation and feature wishes.

## [0.9.21.6] - 2026-10-10

### Fixed
- 📱 **Mobile FAB.** Fixed the race condition where the menu was invisible and the overlay blocked interaction.

## [0.9.21.5] - 2026-10-10

### Improved
- 📱 **Mobile UX.** Expanded the touch target for the `MobileFab` component using an invisible hitbox, ensuring better responsiveness on mobile devices.

## [0.9.21.3] - 2026-10-10

### Fixed
- 🛠️ **Alembic Migrations.** Fixed a malformed migration script (`0005_fix_workspaces_autoincrement.py`) that caused application startup failures.

## [0.9.21.1] - 2026-10-09

### Added
- 📊 **Llama Metrics.** Live token rates and detailed generation statistics (prompt, reasoning, response, etc.) during requests.
- 📁 **Enhanced File Browser.** Improved UI with customizable columns (size, modified, created) and "touch" functionality for modification dates.

## [0.9.21] - 2026-08-04

### Added
- 📊 **Usage has its own Settings page.** See your token activity, active streaks, favorite models, busy days, and most used tools in one place.
- 🛠️ **Tool approval has its own Admin page.** Admins can choose the review model and decide which built-in tools can run automatically.

### Changed
- 🤖 **Agent chats can start from Home.** Coding agents can now answer even when a chat is not attached to a workspace.
- 🌐 **Browser sessions recover more smoothly.** Browser streaming catches up faster when video falls behind and cleans up more reliably when a session closes.
- 🧰 **OpenCode on Docker is easier to connect.** Computer now tries the right host address when needed and gives clearer setup guidance if it cannot connect.
- 📝 **More C and C++ files open with the right language.** Files ending in `.cc`, `.cxx`, `.hh`, and `.hxx` are now recognized.

### Fixed
- 💬 **Empty replies are retried instead of getting stuck.** If a chat service sends back nothing useful, Computer now tries again before showing a failure.
- 🔊 **Text-to-speech cleans up after playback.** Listening to a message no longer leaves old audio resources around.
- 🧰 **Deleted agent profiles stay deleted right away.** Removing a saved agent now saves the change immediately.
- 💻 **Terminal and browser sessions close more cleanly.** Leaving a session is less likely to leave old listeners or other connections behind.
- 📱 **Signal message edits work more naturally.** Updated replies are now sent as edits when Signal supports it.

## [0.9.20] - 2026-08-01

### Added
- 🔍 **Enhanced File Search.** Improved `search_files` with path, context-lines, and paging modes.
- 📜 **Terminal Scrollback.** Configurable terminal session history via `terminal.scrollback_kb`.
- 📅 **Workspace Schedules UI.** Visual interface for managing workspace-scoped schedules in the sidebar.
- 👁️ **Workspace Watch.** Real-time filesystem monitoring via `inotify` for workspace changes.

### Changed
- 🤖 **Agent chats can start from Home.** Coding agents can now answer even when a chat is not attached to a workspace.
- 🌐 **Browser sessions recover more smoothly.** Browser streaming catches up faster when video falls behind and cleans up more reliably when a session closes.
- 🧰 **OpenCode on Docker is easier to connect.** Computer now tries the right host address when needed and gives clearer setup guidance if it cannot connect.
- 📝 **More C and C++ files open with the right language.** Files ending in `.cc`, `.cxx`, `.hh`, and `.hxx` are now recognized.

### Fixed
- 💬 **Empty replies are retried instead of getting stuck.** If a chat service sends back nothing useful, Computer now tries again before showing a failure.
- 🔊 **Text-to-speech cleans up after playback.** Listening to a message no longer leaves old audio resources around.
- 🧰 **Deleted agent profiles stay deleted right away.** Removing a saved agent now saves the change immediately.
- 💻 **Terminal and browser sessions close more cleanly.** Leaving a session is less likely to leave old listeners or other connections behind.
- 📱 **Signal message edits work more naturally.** Updated replies are now sent as edits when Signal supports it.

## [0.9.19] - 2026-07-31

### Changed
- 🗂️ **Chat branching from Open WebUI.** Regenerating or editing a message in Open WebUI now creates proper branches in the cptr sidebar, just like it does in OWUI. Requires custom headers on the OWUI connection (copy from Gateway settings).
- 📡 **More header templates.** Gateway settings now shows the full recommended header config for Open WebUI connections, including message and task type forwarding. One-click copy. Requires Open WebUI ≥ 0.9.7.

### Fixed
- 🐛 **Chat metadata could be empty on second turn.** Fixed an operator precedence issue in message resolution.

## [0.9.18] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.9.17] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.9.16] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.9.15] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.9.14] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.9.13] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.9.12] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.9.11] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.9.10] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.9.9] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.9.8] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.9.7] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.9.6] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.9.5] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.9.4] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.9.3] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.9.2] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.9.1] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.9.0] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.8.9] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.8.8] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.8.7] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.8.6] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.8.5] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.8.4] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.8.3] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.8.2] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.8.1] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.8.0] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.7.9] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.7.8] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.7.7] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.7.6] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.7.5] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.7.4] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.7.3] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.7.2] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.7.1] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.7.0] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.6.9] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.6.8] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.6.7] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.6.6] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.6.5] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.6.4] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.6.3] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.6.2] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.6.1] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.6.0] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.5.9] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.5.8] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.5.7] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.5.6] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.5.5] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.5.4] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.5.3] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.5.2] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.5.1] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.5.0] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.4.9] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.4.8] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.4.7] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.4.6] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.4.5] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.4.4] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.4.3] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.4.2] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.4.1] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.4.0] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.3.9] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.3.8] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.3.7] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.3.6] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.3.5] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.3.4] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.3.3] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.3.2] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.3.1] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.3.0] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.2.9] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.2.8] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.2.7] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.2.6] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.2.5] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.2.4] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.2.3] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.2.2] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.2.1] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.2.0] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.1.9] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.1.8] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.1.7] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.1.6] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.1.5] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.

## [0.1.4] - 2026-07-31

### Added
- 🖼️ **Image generation.** Ask the AI to create images directly in the chat.

## [0.1.3] - 2026-07-31

### Added
- 🎙️ **Voice mode.** Talk to the AI using your microphone.

## [0.1.2] - 2026-07-31

### Added
- 📱 **PWA support.** Install Computer as a standalone app on your device.

## [0.1.1] - 2026-07-31

### Added
- 🌐 **Browser access.** Let the AI browse the web to find information.

## [0.1.0] - 2026-07-31

### Added
- 🤖 **Codex agent.** Connect Codex as an AI backend. Configure the command path and model list from the new Agents tab in admin settings.

## [0.0.9] - 2026-07-31

### Added
- 🧠 **Memory.** The AI can now remember things about you and your projects. Memories are stored per user and per workspace, and are automatically included in future conversations. You can view, edit, and delete memories from the new Memory tab in Settings. Admins can also turn on background memory review, which lets the AI quietly pick up on preferences and patterns as you chat.

## [0.0.8] - 2026-07-31

### Added
- 🖼️ **Image understanding.** The AI can now read and describe images from your workspace. Open a screenshot or image file and it just works, across all providers.
- 🎨 **Image generation and editing.** Ask the AI to create or edit images right from the chat. Generated images are saved to your workspace and displayed inline in the conversation. Supports any OpenAI-compatible image API. Configure from the new Images tab in admin settings.

## [0.0.7] - 2026-07-31

### Added
- 🧠 **Reasoning display.** Models that think before responding (like o3 or Claude with extended thinking) now show their reasoning in the chat. Thought steps appear as collapsible sections you can expand to see what the AI was considering.

## [0.0.6] - 2026-07-31

### Added
- 🕵️ **SearXNG web search.** Choose SearXNG in Web settings and connect Computer to your own search instance.

## [0.0.5] - 2026-07-31

### Added
- 🔍 **Better chat search.** Searching your chats now looks at chat IDs, titles, summaries, and message content all at once, with smarter ranking. Exact and prefix matches on titles and IDs show up first, then summary matches, then message content. You can also filter by workspace and choose whether to include sub-agent chats.

## [0.0.4] - 2026-07-31

### Added
- 🎙️ **Voice dictation in the terminal.** The mobile shortcut bar now has a microphone button that lets you dictate text directly into the terminal using speech recognition. Speak your message, and cptr will transcribe it, send it to the AI, and read the response back to you out loud. The mic re-arms automatically so you can have a back-and-forth conversation without touching the screen.

## [0.0.3] - 2026-07-31

### Added
- 📊 **Usage Dashboard.** View token usage and active streaks in a new Usage tab in settings.

## [0.0.2] - 2026-07-31

### Added
- 🚀 **Automatic Deployment.** The system now handles deployments to the main branch automatically after feature verification.

## [0.0.1] - 2026-07-31

### Added
- 🛠️ **Tool-calling logs.** View detailed logs of all tool calls and their responses in a new Logs tab in Admin settings.

## [0.0.0] - 2026-07-31

### Added
- 🤖 **Sub-agent support.** The AI can now spawn sub-agents to handle specialized tasks in parallel.