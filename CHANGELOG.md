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