# RXT ENGINE Discord Bot

### Overview
RXT ENGINE is a multi-functional Discord bot designed for community management and server automation. It features a futuristic cyberpunk aesthetic, having been rebranded from its previous "VAAZHA" identity. The bot is fully operational and provides comprehensive moderation tools, karma system, ticket management, and CAPTCHA-based verification.

### User Preferences
- Professional futuristic cyberpunk aesthetic
- Clean, modern UI without emojis in code
- Consolidated branding through brand_config.py
- Focus on automation, moderation, and community engagement

## Recent Changes

### November 21, 2025 - Security System Removal (CAPTCHA Verification Retained)
- 🔄 **Complete Security System Removal**
  - Removed all automated security features: anti-spam, anti-raid, anti-nuke, malware filters, timeout system, auto-warning system
  - Removed enhanced_security.py functionality (converted to placeholder file for import compatibility)
  - Removed timeout_system.py completely (bad words detection, spam detection, link filtering)
  - Removed all security event handlers from main.py (permission monitoring, webhook protection, mass action detection)
  - Removed security configuration commands: `/security-config`, `/security-whitelist`, `/raid-mode`, `/warn`, `/warnings`, `/clearwarnings`, `/security-timeout-channel`, `/security-status`, `/timeout-settings`, `/remove-timeout`, `/timeout-stats`
  - Cleaned up setup_commands.py to remove timeout and security log channels
  - Updated help command to reflect only available features
  
- ✅ **CAPTCHA Verification System Retained**
  - `/verification-setup` command fully functional
  - CAPTCHA generation and validation working
  - Verification logging routes to moderation channel
  - All verification features preserved and operational

- 📊 **Command Count**
  - Reduced from 56 commands to 46 commands
  - All removed commands were security-related
  - Core functionality preserved (moderation, karma, tickets, reaction roles, etc.)

### System Architecture

**Core Components:**
- **main.py**: Entry point, event handlers, and help command system.
- **brand_config.py**: Centralized branding configuration (colors, constants, footer).
- **keep_alive.py**: Flask web server for bot uptime monitoring.

**Modular Design:**
The bot's functionalities are organized into distinct modules:
- **xp_commands.py**: Manages the karma/XP system.
- **moderation_commands.py**: Provides moderation tools (ban, kick, mute, voice moderation).
- **setup_commands.py**: Handles server configuration and setup.
- **communication_commands.py**: Facilitates announcements, messages, and DM tools.
- **ticket_system.py**: Implements a support ticket system.
- **reaction_roles.py**: Manages reaction-based role assignments.
- **security_system.py**: Contains CAPTCHA verification system only.
- **timed_roles.py**: Manages timed role assignments.
- **autorole.py**: Handles auto-role assignment for new members.
- **voice_commands.py**: Voice channel moderation commands.

**Visual Systems:**
- **profile_cards.py**: Generates futuristic profile cards using PIL.
- **captcha_generator.py**: Generates unique CAPTCHA images for verification.
- **global_logging.py**: Centralized logging system for server events.
- **server_list.py**: Monitors and tracks server list.

**UI/UX and Theming:**
- **RXT ENGINE Quantum Purple Theme**: Utilizes a consistent color scheme across all embeds and notifications.
- **Brand Colors**: Primary (#8A4FFF - Quantum Purple), Secondary (#4F8CFF - Hyper Blue), Accent (#00E68A - Neon Green), Warning (#FFD700 - Gold), Error (#FF4444 - Red), Background (#0A0A0F - Deep Space), Text (#E0E0E0 - Silver).
- **Consistent Branding**: All branding elements are centralized in `brand_config.py`.

**Key Features:**
- **CAPTCHA Verification**: Secure, modal-based CAPTCHA challenge using PIL-generated images for user verification.
- **Karma/XP System**: Community recognition and leveling system with custom rank cards.
- **Ticket System**: Comprehensive support ticket management with categories and custom fields.
- **Reaction Roles**: Role assignment through interactive reactions.
- **Timed Roles**: Assign roles to users for specific time periods with automatic removal.
- **Auto Role**: Automatically assign roles to new members on join.
- **Moderation Tools**: Kick, ban, nuke, voice moderation (mute, unmute, move, kick, lock/unlock, limit).
- **Communication Tools**: Announcements, embeds, polls, reminders, DM management.
- **Profile Cards**: Beautiful profile cards with circular avatars, karma stats, and modern design.
- **Global Logging**: Centralized logging for all significant server events across multiple servers.
- **Organized Log Channels**: Automatic creation of categorized log channels for different bot activities.

**Architectural Decisions:**
- Centralized branding via `brand_config.py` for consistency.
- PIL image generation uses `BrandColorsRGB` for compatibility.
- Owner mentions are clickable using the `BOT_OWNER_ID` environment variable.
- Focus on a professional, modern, and futuristic theme.
- Security features removed except CAPTCHA verification to streamline bot functionality.

### External Dependencies
- **discord.py**: Python API wrapper for Discord.
- **motor**: Asynchronous MongoDB driver for database interactions.
- **Pillow (PIL)**: Used for image generation, particularly for profile cards and CAPTCHAs.
- **Flask**: Utilized for the `keep_alive.py` web server to maintain bot uptime.
- **MongoDB**: Primary database for persistent storage, including server configurations, user data, tickets, logs, reaction roles, and karma stats.
