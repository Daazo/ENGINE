
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="setecocategory", description="🪙 Setup economy category with organized channels")
@app_commands.describe(category="Category to organize economy channels")
async def setup_economy_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    try:
        # Store the category
        await update_server_data(interaction.guild.id, {'economy_category': str(category.id)})
        
        # Get category permissions to inherit
        overwrites = category.overwrites
        
        # Create economy channels with cool names and emojis
        channels_to_create = [
            ("📋-vaazha-info", "Vaazha Coins economy features and rules! 📖", True),  # Bot-only channel
            ("💰-coin-vault", "Check your balance, claim daily & weekly rewards! 🪙", False),
            ("🍌-banana-jobs", "Work Kerala-themed jobs and earn Vaazha Coins! 🌴", False),
            ("🏆-rich-leaderboard", "See who's the richest in our community! 💎", False),
            ("🛒-vaazha-store", "Buy karma points and exclusive items! ✨", False)
        ]
        
        created_channels = []
        info_channel = None
        
        for channel_name, description, bot_only in channels_to_create:
            # Check if channel already exists
            existing_channel = discord.utils.get(category.channels, name=channel_name)
            if not existing_channel:
                # Create channel with appropriate permissions
                if bot_only:
                    # Info channel - only bot can send messages, others can read
                    info_overwrites = overwrites.copy()
                    # Remove send_messages permission for all roles that have category access
                    for role_or_member in info_overwrites:
                        if info_overwrites[role_or_member].send_messages is not False:
                            info_overwrites[role_or_member] = discord.PermissionOverwrite(
                                read_messages=True,
                                send_messages=False
                            )
                    # Give bot send message permission
                    info_overwrites[interaction.guild.me] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )
                    
                    channel = await interaction.guild.create_text_channel(
                        name=channel_name,
                        category=category,
                        overwrites=info_overwrites,
                        topic=description
                    )
                    info_channel = channel
                else:
                    # Regular channels inherit category permissions
                    channel = await interaction.guild.create_text_channel(
                        name=channel_name,
                        category=category,
                        overwrites=overwrites,
                        topic=description
                    )
                created_channels.append(channel)
            else:
                if bot_only:
                    info_channel = existing_channel
        
        # Update server data with channel IDs
        economy_channels = {
            'info_channel': discord.utils.get(category.channels, name="📋-vaazha-info"),
            'balance_channel': discord.utils.get(category.channels, name="💰-coin-vault"),
            'work_channel': discord.utils.get(category.channels, name="🍌-banana-jobs"),
            'richest_channel': discord.utils.get(category.channels, name="🏆-rich-leaderboard"),
            'store_channel': discord.utils.get(category.channels, name="🛒-vaazha-store")
        }
        
        channel_ids = {k: str(v.id) if v else None for k, v in economy_channels.items()}
        await update_server_data(interaction.guild.id, {'economy_channels': channel_ids})
        
        # Send Vaazha Coins info embed to the info channel
        if info_channel:
            info_embed = discord.Embed(
                title="🪙 **VAAZHA COINS ECONOMY** 🍌",
                description="*Welcome to God's Own Country's official currency system!*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                color=0xf1c40f
            )
            info_embed.add_field(
                name="💰 **How to Earn Coins**",
                value="🌅 **Daily Rewards:** `/daily` - 50+ coins every 24h with streak bonuses\n🗓️ **Weekly Jackpot:** `/weekly` - 300+ coins every 7 days\n💼 **Work Jobs:** `/work` - Kerala-themed jobs (20-100 coins/hour)\n🎰 **Mini-Games:** Slots, trivia, and more!\n✨ **Random Bonuses:** Lucky finds and special events",
                inline=False
            )
            info_embed.add_field(
                name="🛒 **How to Spend Coins**",
                value="⭐ **Buy Karma:** `/buykarma` - 1 karma = 10 coins\n🏦 **Banking:** Deposit coins for safekeeping\n🤝 **Trading:** Send coins to other members\n🎰 **Gambling:** Test your luck with slots\n🏆 **Future Store:** More items coming soon!",
                inline=False
            )
            info_embed.add_field(
                name="🎮 **Available Games**",
                value="🎰 **Banana Slots:** Bet 10-500 coins on Kerala-themed slots\n🧠 **Kerala Trivia:** Answer questions about God's Own Country\n🍌 **Banana Hunt:** Find hidden bananas for rewards\n📊 **Leaderboards:** Compete to be the richest!",
                inline=False
            )
            info_embed.add_field(
                name="🏦 **Banking System**",
                value="💰 **Deposit:** Keep coins safe in your bank account\n💸 **Withdraw:** Take coins out when needed\n📈 **Interest:** Earn passive income on stored coins\n🔒 **Security:** Protected from theft and loss",
                inline=False
            )
            info_embed.add_field(
                name="📋 **Important Rules**",
                value="⚠️ **No Cheating:** Alt accounts and exploits are forbidden\n🤝 **Fair Trading:** No scamming or forced trades\n⏰ **Cooldowns:** Respect command cooldowns (daily, work, etc.)\n🎯 **Channel Usage:** Use designated channels for specific commands\n🛡️ **Admin Actions:** Coin manipulation is logged and monitored",
                inline=False
            )
            info_embed.add_field(
                name="✨ **Special Features**",
                value="🔥 **Daily Streaks:** More consecutive days = bigger bonuses\n🎊 **Random Events:** Surprise bonuses and community events\n🌴 **Kerala Theme:** Coconuts, bananas, backwaters, and spices\n📊 **Statistics:** Track your total earned, spent, and rank\n🤖 **Auto-moderation:** Fair play enforcement",
                inline=False
            )
            info_embed.set_footer(text="🌴 Made with ❤️ from God's Own Country • Use /help for all commands!", icon_url=interaction.guild.me.display_avatar.url)
            info_embed.set_thumbnail(url="https://i.imgur.com/fK4Q5u6.png")  # Banana/coin themed image
            
            await info_channel.send(embed=info_embed)
        
        embed = discord.Embed(
            title="✅ Economy Category Setup Complete!",
            description=f"**Category:** {category.mention}\n**Channels Created:** {len(created_channels)}\n\n🪙 **Economy Channels:**\n" +
                       f"📋 Info & Rules: {economy_channels['info_channel'].mention if economy_channels['info_channel'] else 'Already exists'}\n" +
                       f"💰 Balance & Rewards: {economy_channels['balance_channel'].mention if economy_channels['balance_channel'] else 'Already exists'}\n" +
                       f"🍌 Work & Jobs: {economy_channels['work_channel'].mention if economy_channels['work_channel'] else 'Already exists'}\n" +
                       f"🏆 Rich Leaderboard: {economy_channels['richest_channel'].mention if economy_channels['richest_channel'] else 'Already exists'}\n" +
                       f"🛒 Vaazha Store: {economy_channels['store_channel'].mention if economy_channels['store_channel'] else 'Already exists'}",
            color=0xf1c40f
        )
        embed.set_footer(text="🌴 Economy system organized and ready!")
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"🪙 [ECONOMY SETUP] Economy category set up by {interaction.user}")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting up economy category: {str(e)}", ephemeral=True)

@bot.tree.command(name="setgamecategory", description="🎮 Setup game category with mini-game channels")
@app_commands.describe(category="Category to organize game channels")
async def setup_game_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    try:
        # Store the category
        await update_server_data(interaction.guild.id, {'game_category': str(category.id)})
        
        # Get category permissions to inherit
        overwrites = category.overwrites
        
        # Create game channels with cool names and emojis
        channels_to_create = [
            ("🎰-banana-slots", "Try your luck with our Kerala-themed slot machine! 🍌"),
            ("🧠-kerala-trivia", "Test your knowledge about God's Own Country! 🌴")
        ]
        
        created_channels = []
        
        for channel_name, description in channels_to_create:
            # Check if channel already exists
            existing_channel = discord.utils.get(category.channels, name=channel_name)
            if not existing_channel:
                channel = await interaction.guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=description
                )
                created_channels.append(channel)
        
        # Update server data with channel IDs
        game_channels = {
            'slots_channel': discord.utils.get(category.channels, name="🎰-banana-slots"),
            'trivia_channel': discord.utils.get(category.channels, name="🧠-kerala-trivia")
        }
        
        channel_ids = {k: str(v.id) if v else None for k, v in game_channels.items()}
        await update_server_data(interaction.guild.id, {'game_channels': channel_ids})
        
        embed = discord.Embed(
            title="✅ Game Category Setup Complete!",
            description=f"**Category:** {category.mention}\n**Channels Created:** {len(created_channels)}\n\n🎮 **Game Channels:**\n" +
                       f"🎰 Banana Slots: {game_channels['slots_channel'].mention if game_channels['slots_channel'] else 'Already exists'}\n" +
                       f"🧠 Kerala Trivia: {game_channels['trivia_channel'].mention if game_channels['trivia_channel'] else 'Already exists'}",
            color=0xe67e22
        )
        embed.set_footer(text="🎮 Game zone ready for action!")
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"🎮 [GAME SETUP] Game category set up by {interaction.user}")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting up game category: {str(e)}", ephemeral=True)

@bot.tree.command(name="setbankcategory", description="🏦 Setup bank category with financial channels")
@app_commands.describe(category="Category to organize banking channels")
async def setup_bank_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    try:
        # Store the category
        await update_server_data(interaction.guild.id, {'bank_category': str(category.id)})
        
        # Get category permissions to inherit
        overwrites = category.overwrites
        
        # Create banking channels with cool names and emojis
        channels_to_create = [
            ("🏦-coin-deposits", "Safely store your Vaazha Coins in the bank! 💰"),
            ("💸-coin-withdrawals", "Withdraw your stored coins when needed! 🪙"),
            ("🤝-coin-trading", "Trade coins with other community members! 📈")
        ]
        
        created_channels = []
        
        for channel_name, description in channels_to_create:
            # Check if channel already exists
            existing_channel = discord.utils.get(category.channels, name=channel_name)
            if not existing_channel:
                channel = await interaction.guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=description
                )
                created_channels.append(channel)
        
        # Update server data with channel IDs
        bank_channels = {
            'deposit_channel': discord.utils.get(category.channels, name="🏦-coin-deposits"),
            'withdraw_channel': discord.utils.get(category.channels, name="💸-coin-withdrawals"),
            'trade_channel': discord.utils.get(category.channels, name="🤝-coin-trading")
        }
        
        channel_ids = {k: str(v.id) if v else None for k, v in bank_channels.items()}
        await update_server_data(interaction.guild.id, {'bank_channels': channel_ids})
        
        embed = discord.Embed(
            title="✅ Bank Category Setup Complete!",
            description=f"**Category:** {category.mention}\n**Channels Created:** {len(created_channels)}\n\n🏦 **Banking Channels:**\n" +
                       f"🏦 Deposits: {bank_channels['deposit_channel'].mention if bank_channels['deposit_channel'] else 'Already exists'}\n" +
                       f"💸 Withdrawals: {bank_channels['withdraw_channel'].mention if bank_channels['withdraw_channel'] else 'Already exists'}\n" +
                       f"🤝 Trading: {bank_channels['trade_channel'].mention if bank_channels['trade_channel'] else 'Already exists'}",
            color=0x2ecc71
        )
        embed.set_footer(text="🏦 Banking system organized and secure!")
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"🏦 [BANK SETUP] Bank category set up by {interaction.user}")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting up bank category: {str(e)}", ephemeral=True)
