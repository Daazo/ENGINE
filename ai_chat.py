import os
import discord
from discord import app_commands
from discord.ext import commands
import re
from datetime import datetime
from google import genai
from google.genai import types

from brand_config import BrandColors, BOT_FOOTER, VisualElements, create_info_embed, create_error_embed as brand_error_embed, create_warning_embed

# IMPORTANT: KEEP THIS COMMENT
# Integration: blueprint:python_gemini
# Using Gemini 2.5 Flash for fast AI responses and Gemini 2.0 Flash for image generation

# Module-level variables (set by setup function)
bot = None
db = None
has_permission = None
log_action = None
create_error_embed = None
create_permission_denied_embed = None
_setup_complete = False

# Initialize Gemini client
try:
    gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    print("✅ Gemini AI client initialized")
except Exception as e:
    gemini_client = None
    print(f"⚠️ Gemini AI client failed to initialize: {e}")

def setup(bot_instance, db_instance, permission_func, log_func, error_embed_func, permission_denied_func):
    """Setup the AI chat module with bot instance and helper functions"""
    global bot, db, has_permission, log_action, create_error_embed, create_permission_denied_embed, _setup_complete
    
    # Prevent double setup
    if _setup_complete:
        return
    
    bot = bot_instance
    db = db_instance
    has_permission = permission_func
    log_action = log_func
    create_error_embed = error_embed_func
    create_permission_denied_embed = permission_denied_func
    
    # Register the command after bot is set
    bot.tree.command(name="set-ai-channel", description="🤖 Set the AI chat channel (Owner/Main Moderator only)")(
        app_commands.describe(channel="Channel where AI will respond to messages")(set_ai_channel_command)
    )
    
    _setup_complete = True

# Image generation keywords
IMAGE_KEYWORDS = [
    'create', 'generate', 'make', 'draw', 'design', 'paint', 'sketch',
    'image', 'picture', 'photo', 'illustration', 'art', 'artwork',
    'logo', 'banner', 'wallpaper', 'icon', 'graphic'
]

def is_image_request(message_content: str) -> bool:
    """Detect if user is requesting image generation"""
    content_lower = message_content.lower()
    
    # Check for common image generation patterns
    image_patterns = [
        r'\b(create|generate|make|draw|design)\s+(a|an|me)?\s*(image|picture|photo|logo|art)',
        r'\b(image|picture|photo|logo|art)\s+of\b',
        r'\bshow\s+me\s+(a|an)\s+(picture|image|photo)',
    ]
    
    for pattern in image_patterns:
        if re.search(pattern, content_lower):
            return True
    
    # Check if message contains multiple image-related keywords
    keyword_count = sum(1 for keyword in IMAGE_KEYWORDS if keyword in content_lower)
    return keyword_count >= 2

async def generate_ai_image(prompt: str, temp_path: str) -> bool:
    """Generate image using Gemini"""
    try:
        if not gemini_client:
            print(f"❌ [AI IMAGE ERROR] Gemini client is None")
            return False
        
        print(f"🎨 [AI IMAGE] Calling Gemini API for image generation...")
        # IMPORTANT: Use gemini-2.5-flash-image for image generation (production model)
        # Integration: blueprint:python_gemini
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE']
            )
        )
        
        if not response.candidates:
            print(f"❌ [AI IMAGE ERROR] No candidates in response")
            return False
        
        content = response.candidates[0].content
        if not content or not content.parts:
            print(f"❌ [AI IMAGE ERROR] No content or parts in response")
            return False
        
        for part in content.parts:
            if part.text:
                print(f"🎨 [AI IMAGE] Model response text: {part.text[:100]}...")
            elif part.inline_data and part.inline_data.data:
                with open(temp_path, 'wb') as f:
                    f.write(part.inline_data.data)
                print(f"✅ [AI IMAGE] Image saved to {temp_path}")
                return True
        
        print(f"❌ [AI IMAGE ERROR] No inline_data found in response parts")
        return False
    except Exception as e:
        error_str = str(e)
        print(f"❌ [AI IMAGE ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        # Check if it's a quota error
        if "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            print(f"⚠️ [AI IMAGE] Quota exceeded - user needs to wait or upgrade their plan")
        
        return False

async def get_ai_response(prompt: str) -> str:
    """Get AI text response from Gemini"""
    try:
        if not gemini_client:
            print(f"❌ [AI TEXT ERROR] Gemini client is None")
            return "**✗ AI CORE OFFLINE**\nThe quantum AI core is currently unavailable. Please contact a server admin."
        
        print(f"💬 [AI TEXT] Calling Gemini API for text generation...")
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        result = response.text or "I couldn't generate a response. Please try again."
        print(f"✅ [AI TEXT] Got response: {result[:100]}...")
        return result
    except Exception as e:
        error_str = str(e)
        print(f"❌ [AI TEXT ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        # Check if it's a quota error
        if "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            return "**⚠ QUANTUM CORE LIMIT REACHED**\nAI quota temporarily exhausted. Please try again in a few moments."
        
        return "**✗ PROCESSING ERROR**\nThe quantum core encountered an anomaly. Please try again."

async def set_ai_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the AI chat channel for the server (registered dynamically during setup)"""
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(
            embed=create_permission_denied_embed("Main Moderator"),
            ephemeral=True
        )
        return
    
    try:
        if db is not None:
            await db.ai_settings.update_one(
                {'guild_id': str(interaction.guild.id)},
                {'$set': {
                    'ai_channel_id': str(channel.id),
                    'setup_by': str(interaction.user.id),
                    'setup_at': datetime.utcnow()
                }},
                upsert=True
            )
        
        embed = discord.Embed(
            title="🤖 AI Chat Channel Set",
            description=f"**AI Channel:** {channel.mention}\n**Setup by:** {interaction.user.mention}\n**Status:** Active",
            color=BrandColors.PRIMARY
        )
        embed.add_field(
            name="💬 How It Works",
            value="✓ Just type normally in the AI channel\n✓ No commands needed\n✓ AI auto-detects image requests\n✓ Powered by Gemini 1.5 Flash",
            inline=False
        )
        embed.set_footer(text=BOT_FOOTER)
        
        await interaction.response.send_message(embed=embed)
        await log_action(
            interaction.guild.id,
            "ai_chat",
            f"🤖 [AI CHANNEL SET] {interaction.user} set AI channel to {channel.mention}"
        )
        
        # Global logging
        try:
            from advanced_logging import send_global_log
            await send_global_log(
                "ai_chat",
                f"**🤖 AI Channel Setup**\n**Server:** {interaction.guild.name}\n**Channel:** {channel.mention}\n**Setup by:** {interaction.user.mention}",
                interaction.guild
            )
        except:
            pass
            
    except Exception as e:
        await interaction.response.send_message(
            embed=create_error_embed(f"Failed to set AI channel: {str(e)}"),
            ephemeral=True
        )

async def handle_ai_message(message):
    """Handle AI chat in designated channels (called from main on_message handler)"""
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Ignore if not in a guild
    if not message.guild:
        return
    
    # Check if AI is enabled for this server
    if db is None:
        print(f"⚠️ [AI CHAT] DB is None, skipping message from {message.author}")
        return
    
    try:
        ai_settings = await db.ai_settings.find_one({'guild_id': str(message.guild.id)})
        print(f"🔍 [AI CHAT DEBUG] Guild ID: {message.guild.id}, Channel ID: {message.channel.id}, AI Settings: {ai_settings}")
        
        # No AI channel set
        if not ai_settings or not ai_settings.get('ai_channel_id'):
            print(f"⚠️ [AI CHAT] No AI settings found for guild {message.guild.id}")
            return
        
        # Check if message is in the AI channel
        if str(message.channel.id) != ai_settings.get('ai_channel_id'):
            print(f"⚠️ [AI CHAT] Message in wrong channel: {message.channel.id} != {ai_settings.get('ai_channel_id')}")
            return
        
        print(f"✅ [AI CHAT] Processing message in AI channel: {message.content[:100]}")
        print(f"🔍 [AI CHAT] Gemini client status: {gemini_client is not None}")
        
        # Check if Gemini client is initialized
        if not gemini_client:
            print(f"❌ [AI CHAT] Gemini client is None!")
            embed = discord.Embed(
                title="✗ AI SERVICE OFFLINE",
                description=f"The AI core is currently unavailable.\n\n**Action Required:** Server admin needs to configure the API key.\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await message.channel.send(embed=embed)
            return
        
        # Show typing indicator
        async with message.channel.typing():
            # Check if this is an image generation request
            if is_image_request(message.content):
                print(f"🎨 [AI CHAT] Detected image request: {message.content[:50]}")
                # Image generation disabled - show themed message
                embed = discord.Embed(
                    title="◆ IMAGE GENERATION UNAVAILABLE",
                    description=f"**Requested:** {message.content[:100]}{'...' if len(message.content) > 100 else ''}\n\n**Status:** RXT ENGINE is currently operating on the **Free Plan**.\n\nImage generation requires a premium API subscription. Text-based AI chat is fully available!\n{VisualElements.CIRCUIT_LINE}",
                    color=BrandColors.PRIMARY
                )
                embed.add_field(
                    name="💬 What You Can Do",
                    value="◆ Ask questions\n◆ Get information\n◆ Have conversations\n◆ Get help with tasks",
                    inline=False
                )
                embed.set_footer(text=BOT_FOOTER)
                await message.reply(embed=embed)
                print(f"🎨 [AI CHAT] Sent free plan message for image request")
            else:
                # Generate text response
                print(f"💬 [AI CHAT] Generating text response for: {message.content[:50]}")
                response_text = await get_ai_response(message.content)
                print(f"💬 [AI CHAT] Got response ({len(response_text)} chars): {response_text[:100]}...")
                
                # Split response if too long (Discord limit is 2000 chars)
                if len(response_text) > 2000:
                    # Send in chunks
                    chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                    print(f"✅ [AI CHAT] Sent {len(chunks)} message chunks")
                else:
                    await message.reply(response_text)
                    print(f"✅ [AI CHAT] Sent text response")
                
                # Log the interaction
                await log_action(
                    message.guild.id,
                    "ai_chat",
                    f"🤖 [AI CHAT] {message.author}: {message.content[:50]}"
                )
                
                # Global logging
                try:
                    from advanced_logging import send_global_log
                    await send_global_log(
                        "ai_chat",
                        f"**🤖 AI Chat**\n**User:** {message.author.mention}\n**Query:** {message.content[:100]}",
                        message.guild
                    )
                except:
                    pass
                    
    except Exception as e:
        print(f"❌ [AI CHAT ERROR] {e}")
        embed = discord.Embed(
            title="✗ PROCESSING ERROR",
            description=f"The quantum core encountered an anomaly while processing your request.\n\nPlease try again.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER
        )
        embed.set_footer(text=BOT_FOOTER)
        await message.reply(embed=embed)

print("✅ AI Chat system loaded (Gemini 1.5 Flash)")
