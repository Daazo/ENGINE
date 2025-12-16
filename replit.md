# RXT ENGINE Discord Bot

### Overview
RXT ENGINE is a multi-functional Discord bot designed for comprehensive community management and server automation with a futuristic cyberpunk aesthetic. Its purpose is to provide advanced moderation, a robust karma system, efficient ticket management, secure CAPTCHA-based verification, and AI-powered chat capabilities, aiming to be a central tool for server administration and community engagement.

### User Preferences
- Professional futuristic cyberpunk aesthetic
- Clean, modern UI without emojis in code
- Consolidated branding through brand_config.py
- Focus on automation, moderation, and community engagement

### System Architecture

**Core Components & Modular Design:**
The bot's architecture is modular, with `main.py` serving as the entry point. Key functionalities are organized into distinct modules:
- **`xp_commands.py`**: Karma/XP system.
- **`moderation_commands.py`**: Moderation tools (ban, kick, mute, voice moderation).
- **`setup_commands.py`**: Server configuration.
- **`communication_commands.py`**: Announcements, messages, DMs.
- **`ticket_system.py`**: Support ticket management.
- **`reaction_roles.py`**: Reaction-based role assignments.
- **`rxt_security.py`**: Comprehensive security system (anti-raid, anti-nuke, anti-spam, anti-link, webhook guard, anti-role abuse, Discord native timeout, mass mention protection, whitelist system).
- **`timed_roles.py`**: Timed role assignments.
- **`autorole.py`**: Auto-role for new members.
- **`voice_commands.py`**: Voice channel moderation.
- **`advanced_logging.py`**: Dual logging system (single-channel, multi-channel, cross-server, global).
- **`ai_chat.py`**: Gemini-powered AI chat with image generation.

**Visual Systems:**
- **`profile_cards.py`**: Generates futuristic profile cards.
- **`captcha_generator.py`**: Creates unique CAPTCHA images.

**UI/UX and Theming:**
- **RXT ENGINE Quantum Purple Theme**: Consistent color scheme (`#8A4FFF`, `#4F8CFF`, `#00E68A`, `#FFD700`, `#FF4444`, `#0A0A0F`, `#E0E0E0`) across all embeds and notifications, centralized in `brand_config.py`.

**Key Features:**
- **AI Chat with Gemini**: Natural conversations, automatic image generation, dual logging. Uses `gemini-2.5-flash` for text and `gemini-2.0-flash-preview-image-generation` for images.
- **RXT Security System**: Production-ready, ToS-compliant server protection with 9 modules, integrated with Discord's native timeout API.
- **Advanced Logging System**: Dual logging capabilities (per-server and global bot-wide) with auto-event listeners for message edits/deletions, member events, role/channel updates, and voice activity.
- **Verification System**: Dual-mode verification supporting both CAPTCHA (solve image code) and Button (one-click) verification types, configurable per-server.
- **Karma/XP System**: Community leveling with custom rank cards.
- **Ticket System**: Comprehensive support ticket management.
- **Reaction Roles & Timed/Auto Roles**: Flexible role assignment.
- **Moderation Tools**: Full suite of moderation commands including voice moderation.
- **Communication Tools**: Announcements, embeds, polls, reminders, DMs.
- **Profile Cards**: Visually appealing profile cards with circular avatars.

**Architectural Decisions:**
- Centralized branding via `brand_config.py`.
- PIL image generation uses `BrandColorsRGB` for compatibility.
- Owner mentions are clickable using `BOT_OWNER_ID`.
- Focus on a professional, modern, and futuristic theme.
- Security system utilizes Discord's native timeout API for ToS compliance and integrates with existing moderation and logging.
- Idempotent setup pattern prevents duplicate command registration.
- Comprehensive error handling and logging for production resilience.

### External Dependencies
- **discord.py**: Python API wrapper for Discord.
- **motor**: Asynchronous MongoDB driver for database interactions.
- **Pillow (PIL)**: Used for image generation (profile cards, CAPTCHAs).
- **Flask**: Utilized by `keep_alive.py` for bot uptime monitoring.
- **MongoDB**: Primary database for persistent storage of server configurations, user data, tickets, logs, reaction roles, karma stats, and AI channel settings.
- **Google Gemini API**: For AI chat and image generation capabilities.