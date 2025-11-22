# RXT ENGINE Discord Bot

### Overview
RXT ENGINE is a multi-functional Discord bot designed for community management and server automation. It features a futuristic cyberpunk aesthetic, having been rebranded from its previous "VAAZHA" identity. The bot is fully operational and provides comprehensive moderation tools, karma system, ticket management, and CAPTCHA-based verification.

### User Preferences
- Professional futuristic cyberpunk aesthetic
- Clean, modern UI without emojis in code
- Consolidated branding through brand_config.py
- Focus on automation, moderation, and community engagement

## Recent Changes

### November 22, 2025 - Message Logging & Advanced Logging System (PRODUCTION-READY)
- 📝 **MESSAGE LOGGING SYSTEM**
  - **on_message_delete**: Auto-logs deleted messages to `message-delete` channel
  - **on_message_edit**: Auto-logs message edits to `message-edit` channel with before/after content
  - **Dual Channel System**: Messages routed through advanced logging to appropriate per-server channels
  - **Global Integration**: All message logs also sent to global logging system when configured
  
- 🌐 **ADVANCED LOGGING SYSTEM**
  - **Single Channel Mode**: `/log-channel` - All logs in one channel
  - **Organized Multi-Channel**: `/log-category` - Auto-creates 20+ dedicated channels for:
    - Message Activity: `message-delete`, `message-edit`
    - Security: `security`, `quarantine`, `anti-raid`, `anti-nuke`
    - Moderation: `moderation`, `member-ban`, `member-kick`
    - Server Events: `join-leave`, `role-update`, `channel-update`
    - Systems: `automod`, `voice-log`, `ticket-log`, `karma`, `command-log`, `error-log`, etc.
  - **Cross-Server Logging**: Redirect all logs to another server's category
  - **Global Bot-Wide Logging**: `/setup-global-logging` - Centralized logging for all bot activity
  
- 📊 **Commands** (5 logging commands):
  - `/log-channel` - Set single channel for all logs
  - `/log-category` - Create organized multi-channel logging
  - `/setup-global-logging` - Bot-wide logging (owner only)
  - `/log-status` - Check logging configuration
  - `/log-disable` - Disable all logging
  
- ✨ **Features**:
  - Message delete logs capture author, channel, content, and attachments
  - Message edit logs show before/after content for audit trails
  - Automatic routing to correct channels based on log type
  - Color-coded embeds with RXT ENGINE theme
  - Fallback system for backwards compatibility
  - MongoDB storage for persistent configuration

### November 21, 2025 - RXT SECURITY SYSTEM Implementation (PRODUCTION-READY)
- 🔐 **COMPLETE RXT SECURITY SYSTEM ADDED**
  - **New Module**: rxt_security.py - comprehensive security protection system
  - **Database Schema**: Security configuration storage in MongoDB
  - **ToS-Compliant**: Uses Discord's native timeout API exclusively
  - **Production-Ready**: Architect-verified, fully functional and tested
  
- 🛡️ **Core Security Features** (9 Protection Modules):
  - **Anti-Mass Mention**: Blocks unauthorized @everyone/@here mentions
  - **Anti-Raid**: Detects suspicious join patterns, account age checks, username filtering
  - **Anti-Nuke**: Prevents mass channel/role deletion, mass ban/kick attacks
  - **Anti-Spam/Flood**: Message rate limiting with configurable thresholds
  - **Anti-Link**: Blocks malicious links with domain whitelist support
  - **Webhook Guard**: Detects and removes unauthorized webhooks
  - **Anti-Role Abuse**: Prevents high-permission role creation/escalation
  - **Timeout System**: Discord native timeout with moderator notification channel
  - **Whitelist System**: Users/roles/bots bypass protection
  
- 🔒 **Timeout System**:
  - Uses Discord's native `Member.timeout()` API (ToS-compliant)
  - Optional timeout notification channel for moderator logging
  - Prevents ALL user communication during timeout (messages, reactions, voice, threads)
  - Manual timeout management: `/timeout`, `/untimeout`
  - Proper error handling for permission failures
  
- 🟩 **Whitelist System**:
  - Bypass protection for trusted users, roles, and bots
  - Server owner automatically whitelisted
  - Full whitelist management: `/whitelist add/remove/list`
  
- ⚙️ **Security Commands** (11 new commands):
  - `/security` - Enable/disable/status/config main control panel
  - `/antiraid`, `/antinuke`, `/antilink`, `/antispam`, `/massmention`, `/webhookguard`, `/antirole` - Toggle individual protections
  - `/timeout`, `/untimeout` - Manual timeout management
  - `/whitelist` - Whitelist management for users/roles/bots
  
- 📊 **Command Count**:
  - Added 11 security commands
  - Total: 57 commands synced
  - All security features follow RXT ENGINE Quantum Purple theme
  
- 🏗️ **Technical Architecture**:
  - Idempotent setup prevents duplicate command registration
  - Event listeners use `@bot.listen()` to coexist with existing handlers
  - Proper integration with existing logging system
  - Rate-limit and error handling for production resilience

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
- **security_system.py**: Contains CAPTCHA verification system.
- **rxt_security.py**: Full RXT Security System with anti-raid, anti-nuke, timeout management, and whitelist.
- **timed_roles.py**: Manages timed role assignments.
- **autorole.py**: Handles auto-role assignment for new members.
- **voice_commands.py**: Voice channel moderation commands.
- **advanced_logging.py**: Dual logging system with single-channel, organized multi-channel, cross-server, and global logging modes.

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
- **RXT Security System**: Production-ready comprehensive server protection with 9 modules: anti-raid, anti-nuke, anti-spam, anti-link, webhook guard, anti-role abuse, Discord native timeout, mass mention protection, and whitelist system. ToS-compliant and architect-verified.
- **Advanced Logging System**: Dual logging with single-channel, organized multi-channel, cross-server, and global bot-wide modes. Automatic message delete/edit logging.
- **Message Logging**: Auto-logs all deleted and edited messages with content snapshots for audit trails.
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

**Architectural Decisions:**
- Centralized branding via `brand_config.py` for consistency.
- PIL image generation uses `BrandColorsRGB` for compatibility.
- Owner mentions are clickable using the `BOT_OWNER_ID` environment variable.
- Focus on a professional, modern, and futuristic theme.
- RXT Security System uses Discord's native timeout API for ToS compliance.
- Security system integrates seamlessly with existing moderation and logging infrastructure.
- Idempotent setup pattern prevents duplicate command registration across module imports.

### External Dependencies
- **discord.py**: Python API wrapper for Discord.
- **motor**: Asynchronous MongoDB driver for database interactions.
- **Pillow (PIL)**: Used for image generation, particularly for profile cards and CAPTCHAs.
- **Flask**: Utilized for the `keep_alive.py` web server to maintain bot uptime.
- **MongoDB**: Primary database for persistent storage, including server configurations, user data, tickets, logs, reaction roles, and karma stats.
