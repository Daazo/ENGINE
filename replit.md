# RXT ENGINE Discord Bot

## Overview
RXT ENGINE is a powerful multi-function Discord bot focused on automation, moderation, and server management. Completely rebranded from the previous Kerala-themed "VAAZHA" bot to a futuristic cyberpunk aesthetic.

**Current Version:** 2.0.0  
**Tagline:** "Powering the future of Discord automation"  
**Status:** ✅ Fully operational (requires Discord bot token to run)

## Recent Changes

### November 20, 2025 - Phase 3: Anti-Nuke, Permission Shield, Webhook Protection Implementation
- 🚫 **Anti-Nuke System (Mass Action Detection & Auto-Rollback)**
  - **Mass Ban Detection & Rollback**: Tracks bans via audit logs (default: 5 bans/min), automatically unbans all affected users
  - **Mass Kick Detection & Alert**: Detects kicks in `on_member_remove` via audit logs (default: 5 kicks/min), sends alerts and logs kicked user IDs (**Discord API Limitation**: Automatic re-invitation is not supported by Discord's API - kicked users must be manually re-invited by server administrators)
  - **Mass Role Deletion & Rollback**: Monitors role deletes (default: 3 deletes/min), recreates deleted roles with full permissions
  - **Mass Channel Deletion & Rollback**: Monitors channel deletes (default: 3 deletes/min), recreates deleted channels with settings
  - **Independent Threshold Configuration**: Separate configurable thresholds for bans, kicks, role deletes, and channel deletes via `/security-config`
  - Automatically tracks destructive actions via Discord audit logs
  - Sends critical alerts to security channel when nuke detected
  - DMs server owner with critical alerts and moderator information
  - **Full Auto-Rollback System**:
    - Unbans: Automatically unbans all users when mass ban threshold exceeded
    - Roles: Recreates deleted roles with original permissions, colors, and settings
    - Channels: Recreates deleted text/voice channels with topics, slowmode, and categories
  - Rollback actions logged to security channel with success count
  - Protects against server nuking/raiding attacks with automatic mitigation
  
- 🛡️ **Permission Shield System**
  - Monitors role permission changes in real-time
  - Automatically reverts unauthorized dangerous permission additions:
    - Administrator
    - Manage Server
    - Manage Channels
    - Manage Roles
    - Ban Members
    - Kick Members
    - Manage Webhooks
  - Main moderators exempt from permission shield
  - Automatic permission rollback with detailed alerts
  - Sends alerts to security channel with moderator info
  - Prevents privilege escalation attacks
  - Works on all roles including @everyone
  
- 🔗 **Webhook Protection System**
  - Monitors webhook creation events
  - Automatically deletes unauthorized webhooks
  - Main moderators can create webhooks (whitelisted)
  - Logs all webhook creation/deletion attempts
  - Sends alerts to security channel
  - Prevents webhook-based attacks and spam
  - Tracks webhook deletions for security auditing
  
- ⚙️ **Enhanced /security-config Command**
  - Now supports 8 security features (up from 5):
    - Auto-Timeout @everyone/@here
    - Link Filter
    - Anti-Invite
    - Anti-Spam
    - Anti-Raid
    - **Anti-Nuke (Mass Bans/Kicks/Deletes)** ← NEW
    - **Permission Shield** ← NEW
    - **Webhook Protection** ← NEW
  - Configurable thresholds for anti-nuke detection
  - Simple enable/disable per feature
  - All Phase 3 features log to security channel
  
- 🔧 **Phase 3 Event Handlers Integrated**
  - `on_member_ban` - Detects mass ban attempts
  - `on_guild_role_delete` - Detects mass role deletions
  - `on_guild_channel_delete` - Enhanced with anti-nuke channel deletion check
  - `on_guild_role_update` - Permission shield monitoring
  - `on_webhooks_update` - Webhook protection monitoring
  - All handlers use Discord audit logs to identify responsible moderators
  - Automatic error handling with detailed logging
  
- 🔐 **Full Integration with Phase 1 & Phase 2**
  - Phase 3 works seamlessly with existing security systems
  - All features use RXT ENGINE Quantum Purple theme
  - Unified logging to security channel
  - Consistent alert format across all phases
  - Complete server protection from nuke/raid/permission attacks

### November 20, 2025 - Phase 2: Anti-Spam, Anti-Raid, Link Filter, Anti-Invite Implementation
- ⚡ **Link Filter System**
  - Automatically deletes external links (http://, https://, www.) from non-moderators
  - Respects whitelist system (whitelisted users can post links freely)
  - Configurable via `/security-config` → Link Filter
  - Logs all blocked links to security channel
  - Shows quantum purple notification when link is blocked (auto-deletes after 5s)
  
- 💬 **Anti-Invite System**
  - Blocks Discord invite links (discord.gg, discord.com/invite, discordapp.com/invite)
  - Moderators always exempt from restrictions
  - Whitelist support for trusted users to post invites
  - Configurable allowed channels (invites permitted in specific channels)
  - Logs all blocked invites to security channel
  - RXT ENGINE themed notifications with auto-delete
  
- 💨 **Anti-Spam Detection & Auto-Timeout**
  - Detects repeated messages (3+ identical messages = auto-timeout)
  - Detects message flooding (5+ messages in 5 seconds = auto-timeout)
  - Applies enhanced timeout with role removal and timeout role
  - Configurable timeout duration via `/security-config` duration parameter
  - Moderators exempt from anti-spam detection
  - All spam timeouts logged to security channel
  - Quantum purple notification with reason and duration shown
  
- 🚨 **Anti-Raid System with Auto-Kick**
  - Monitors member joins in real-time
  - Detects raid conditions (default: 5+ joins in 10 seconds)
  - Automatically enables raid mode when threshold exceeded
  - Auto-kicks all new members while raid mode is active
  - Configurable thresholds (join count and time window)
  - Manual raid mode toggle via `/raid-mode` command
  - Sends critical alert to security channel when raid detected
  - All kicked members logged with user ID
  
- ⚙️ **Enhanced /security-config Command**
  - Now supports 5 security features (up from 1):
    - Auto-Timeout @everyone/@here
    - Link Filter
    - Anti-Invite
    - Anti-Spam
    - Anti-Raid
  - Simple enable/disable per feature
  - Duration parameter for timeout-based features
  - Logs all configuration changes
  - RXT ENGINE quantum purple themed responses
  
- 🚨 **New /raid-mode Command**
  - Manually enable/disable raid mode
  - Requires Main Moderator permissions
  - Instant activation/deactivation
  - Shows clear status (enabled = red danger theme, disabled = green success)
  - Logs all manual raid mode changes
  
- 🔗 **Full Integration with Existing Systems**
  - Phase 2 checks integrated into main.py `on_message` handler
  - Anti-Raid check integrated into `on_member_join` handler
  - All Phase 2 features use Phase 1 whitelist framework
  - Security checks execute in correct order (spam → invites → links)
  - All features log to security channel consistently
  - 55 total commands registered (up from 54)

### November 20, 2025 - Phase 1 Bug Fixes & Improvements
- ✅ **Fixed Circular Import Errors in enhanced_security.py**
  - Replaced `bot.user` with `interaction.client.user` in all slash commands
  - Fixed `guild.me` references to use proper null checking
  - Added guild validation checks to all Phase 1 commands
  - All commands now work without "interaction failed" errors
  - Reduced LSP errors from 16 to 5 (remaining are minor type warnings)

- ✅ **Enhanced Error Handling**
  - Commands properly validate guild context before execution
  - DM embeds use proper bot avatar fallbacks
  - Message event handlers use guild.me for avatar references

### November 20, 2025 - Phase 1: Enhanced Security System Implementation
- ⚡ **Enhanced Timeout Role System with Automatic Role Save/Restore**
  - Created `/remove-timeout` command to manually remove timeouts and restore roles
  - Automatically creates "⏰ Timed Out" role with proper permissions
  - Saves all user roles before applying timeout (stored in database)
  - Removes all user roles and applies timeout role during timeout period
  - Automatically restores previous roles when timeout ends or is manually removed
  - Timeout role only grants access to timeout channel (if configured)
  - All other channels become inaccessible during timeout
  - Persistent role data survives bot restarts via MongoDB
  
- 🔐 **Comprehensive Whitelist Framework**
  - New `/security-whitelist` command for managing feature-specific whitelists
  - Whitelist users for: @everyone/@here mentions, post links, discord invites, all security
  - Actions: add, remove, list whitelisted users per feature
  - Whitelisted users bypass specific security restrictions
  - Database-backed persistent whitelists per guild
  - Full RXT ENGINE Quantum Purple theme for all whitelist embeds
  
- 📣 **Auto-Timeout for @everyone/@here Mentions**
  - New `/security-config` command to enable/configure auto-timeout features
  - Automatically detects unauthorized @everyone or @here mentions
  - Deletes offending message immediately
  - Applies enhanced timeout with role removal and timeout role
  - Configurable timeout duration (default: 30 minutes)
  - Respects moderator permissions (junior/main moderators exempt)
  - Respects whitelist system (whitelisted users can mention freely)
  - Sends notification in channel when timeout is applied
  - All logs routed to security log channel
  
- 📁 **New Files Created**
  - `enhanced_security.py` - Phase 1 enhanced security features
  - Integrated with main.py via on_message event handler
  - Seamlessly works with existing timeout_system.py
  
### November 20, 2025 - Enhanced Security Systems & Command Cleanup (Previous)
- ✅ **Enhanced Auto-Timeout System with 100% Isolation**
  - Added `/timeout-channel` command to configure dedicated timeout channel
  - When enabled, timed-out members can ONLY see and chat in the timeout channel
  - All other channels become completely inaccessible during timeout
  - Automatic permission restoration when timeout expires
  - Manual permission restoration via `/remove-timeout` command
  - Background cleanup task runs every 60 seconds to auto-restore expired timeouts
  - Saves and restores previous channel permissions (preserves staff-defined custom overrides)
  - No automatic category/channel creation - manual configuration required
  
- ✅ **CAPTCHA-Based Verification System (Secure Modal-Based)**
  - Visual CAPTCHA challenge with random 6-character codes
  - PIL-based image generator with noise, distortion, and cyberpunk styling
  - Unique CAPTCHA per user (changes for every verification attempt)
  - **Secure modal popup input** - code never visible in channel (100% private)
  - CAPTCHA image and "Enter CAPTCHA Code" button appear together in one message
  - Code submitted through private popup form (no chat messages)
  - Case-insensitive validation for better UX
  - Excludes ambiguous characters (O, 0, I, l, 1) for clarity
  - On success: assigns verified role, optionally removes unverified role
  - On failure: shows clear error message, allows retry
  - Fully integrated with `/verification-setup` command
  - **Removed confusing duplicate verification option from `/security` command**
  - Now only `/verification-setup` is used for CAPTCHA verification (cleaner UX)
  - **Full RXT ENGINE Quantum Purple theme** - all embeds use quantum purple/neon theme
  - Consistent branding across all verification messages with quantum symbols (⚡, ◆, 💠)

### November 19, 2025 - Critical Bug Fixes
- ✅ Fixed `/help` About button interaction failure (removed duplicate view creation)
- ✅ Removed duplicate Contact button from help menu (merged into About section)
- ✅ Fixed ticket panel persistence - now works correctly after bot restarts
  - Added persistent custom_id ("persistent_ticket_select") to TicketCategorySelect
  - TicketSelectionView always includes select component for proper registration
  - Callback validates category existence and shows helpful errors
- ✅ All persistent views properly registered at bot startup

### November 18, 2025 - Complete Rebrand to RXT ENGINE
- ✅ Deleted all economy system files (economy_system.py, economy_setup.py)
- ✅ Created brand_config.py with new color scheme and branding constants
- ✅ Updated all 15+ command modules with new RXT ENGINE branding
- ✅ Removed all Kerala/VAAZHA references from codebase
- ✅ New color scheme: Quantum Purple (#8A4FFF) primary, Hyper Blue (#4F8CFF) secondary
- ✅ Updated footer to "RXT ENGINE • Powered by R!O</>"
- ✅ Fixed all import errors and circular dependencies
- ✅ Bot successfully loads all modules

## Project Architecture

### Core Files
- **main.py** - Main bot entry point, event handlers, help command system
- **brand_config.py** - Centralized branding configuration (colors, constants, footer)
- **keep_alive.py** - Flask web server for bot uptime monitoring

### Command Modules
- **xp_commands.py** - XP/leveling system with rank cards
- **moderation_commands.py** - Moderation tools (ban, kick, mute, warn)
- **setup_commands.py** - Server configuration and setup
- **communication_commands.py** - Announcements, messages, DM tools
- **ticket_commands.py** - Support ticket system
- **reaction_roles.py** - Reaction role management
- **security_commands.py** - Anti-raid, anti-nuke, verification

### Visual Systems
- **profile_cards.py** - PIL-based profile card generation with futuristic design
- **global_logging.py** - Centralized logging system

### Dependencies
- discord.py - Discord API wrapper
- motor - Async MongoDB driver
- Pillow (PIL) - Image generation
- Flask - Web server for keep-alive

## Brand Configuration

### Colors (BrandColors class)
- **PRIMARY**: #8A4FFF (Quantum Purple) - Main accent color
- **SECONDARY**: #4F8CFF (Hyper Blue) - Secondary highlights
- **ACCENT**: #00E68A (Neon Green) - Success/positive actions
- **WARNING**: #FFD700 (Gold) - Warnings and cautions
- **ERROR**: #FF4444 (Red) - Errors and destructive actions
- **BACKGROUND**: #0A0A0F (Deep Space) - Dark backgrounds
- **TEXT**: #E0E0E0 (Silver) - Primary text

### Constants
- **BOT_NAME**: "RXT ENGINE"
- **BOT_VERSION**: "2.0.0"
- **BOT_TAGLINE**: "Powering the future of Discord automation"
- **BOT_FOOTER**: "RXT ENGINE • Powered by R!O</>"
- **BOT_OWNER_NAME**: "R!O</>"
- **BOT_OWNER_DESCRIPTION**: "Creator and developer of RXT ENGINE bot..."

### Owner Mentions
- Bot uses `BOT_OWNER_ID` environment variable for clickable mentions
- DM detection keywords: "@owner", "daazo" (legacy keyword maintained for compatibility)
- Owner mentions are clickable using Discord's `<@{user_id}>` format

## User Preferences
- Professional futuristic cyberpunk aesthetic
- Clean, modern UI without emojis in code
- Consolidated branding through brand_config.py
- Economy features removed (focus on automation/moderation)

## Environment Variables Required
- `DISCORD_BOT_TOKEN` - Discord bot authentication token
- `MONGO_URI` - MongoDB connection string
- `BOT_OWNER_ID` - Discord user ID of bot owner (for clickable mentions)

## Running the Bot
The workflow "RXT ENGINE Bot" runs: `python main.py`

Expected startup sequence:
```
✅ Profile cards system loaded
✅ Global logging system loaded
✅ Server list monitoring system loaded
⚡ RXT ENGINE is starting...
```

If no token is configured, will show: `❌ Invalid bot token!` (this is normal)

## Database
- MongoDB database name: `rxt_engine_bot` (changed from vaazha_bot)
- Collections: servers, users, tickets, logs, reactions, warnings

## Features
### Active Systems
- ⚡ **Karma/XP System** - Community recognition and leveling
- 🛡️ **Security** - Anti-raid, anti-nuke, verification
- 🎫 **Ticket System** - Support ticket management
- 🎭 **Reaction Roles** - Role assignment via reactions
- 📊 **Logging** - Comprehensive server event logging
- 🎨 **Visual Cards** - Profile and server cards with PIL

### Removed Features
- ❌ Economy system (coins, bank, games) - Deleted completely
- ❌ Kerala-themed elements - Replaced with cyberpunk theme

## Architecture Decisions
- Centralized branding via brand_config.py to avoid scattered constants
- PIL image generation uses BrandColorsRGB for compatibility
- Clickable owner mentions using BOT_OWNER_ID environment variable
- Professional modern theme replacing cultural/regional branding
