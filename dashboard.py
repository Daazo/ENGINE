
from flask import Flask, render_template, session, redirect, url_for, request, jsonify, flash
import requests
import os
import asyncio
import discord
from discord.ext import commands
import motor.motor_asyncio
from datetime import datetime, timedelta
import json
from threading import Thread
import time

# Import bot components
from main import bot, get_server_data, update_server_data, db

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Discord OAuth2 settings
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'https://your-repl-url.replit.dev/callback')
DISCORD_BOT_INVITE_URL = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&permissions=8&scope=bot%20applications.commands"

# Discord API URLs
DISCORD_API_BASE = 'https://discord.com/api/v10'
DISCORD_OAUTH_URL = f"{DISCORD_API_BASE}/oauth2/authorize"
DISCORD_TOKEN_URL = f"{DISCORD_API_BASE}/oauth2/token"
DISCORD_USER_URL = f"{DISCORD_API_BASE}/users/@me"
DISCORD_GUILDS_URL = f"{DISCORD_API_BASE}/users/@me/guilds"

def get_user_guilds(access_token):
    """Get user's Discord guilds"""
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(DISCORD_GUILDS_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    return []

def get_user_info(access_token):
    """Get user's Discord info"""
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(DISCORD_USER_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def user_has_permission(guild_id, user_id):
    """Check if user has admin permissions in guild"""
    try:
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
        
        member = guild.get_member(int(user_id))
        if not member:
            return False
        
        # Check if user is owner or has admin permissions
        return member.guild_permissions.administrator or member.id == guild.owner_id
    except:
        return False

@app.route('/')
def index():
    """Dashboard home page"""
    if 'user' not in session:
        return render_template('dashboard_home.html')
    
    # Get user's guilds
    user_guilds = []
    bot_guilds = []
    
    if 'access_token' in session:
        user_guilds = get_user_guilds(session['access_token'])
        # Filter guilds where user has admin permissions
        user_guilds = [guild for guild in user_guilds if guild['permissions'] & 0x8]  # Administrator permission
        
        # Get guilds where bot is present
        for guild in bot.guilds:
            for user_guild in user_guilds:
                if str(guild.id) == user_guild['id']:
                    bot_guilds.append({
                        'id': guild.id,
                        'name': guild.name,
                        'icon': guild.icon.url if guild.icon else None,
                        'member_count': guild.member_count,
                        'in_bot': True
                    })
                    break
    
    return render_template('dashboard.html', 
                         user=session['user'], 
                         user_guilds=user_guilds,
                         bot_guilds=bot_guilds,
                         invite_url=DISCORD_BOT_INVITE_URL)

@app.route('/login')
def login():
    """Redirect to Discord OAuth"""
    oauth_url = f"{DISCORD_OAUTH_URL}?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    return redirect(oauth_url)

@app.route('/callback')
def callback():
    """Discord OAuth callback"""
    code = request.args.get('code')
    if not code:
        flash('Authentication failed!', 'error')
        return redirect(url_for('index'))
    
    # Exchange code for access token
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        
        # Get user info
        user_info = get_user_info(access_token)
        if user_info:
            session['user'] = user_info
            session['access_token'] = access_token
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
    
    flash('Authentication failed!', 'error')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('Successfully logged out!', 'success')
    return redirect(url_for('index'))

@app.route('/server/<guild_id>')
def server_dashboard(guild_id):
    """Server-specific dashboard"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check permissions
    if not user_has_permission(guild_id, session['user']['id']):
        flash('You do not have permission to manage this server!', 'error')
        return redirect(url_for('index'))
    
    # Get server data
    guild = bot.get_guild(int(guild_id))
    if not guild:
        flash('Server not found or bot not in server!', 'error')
        return redirect(url_for('index'))
    
    # Get server configuration from database
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server_data = loop.run_until_complete(get_server_data(guild_id))
    loop.close()
    
    return render_template('server_dashboard.html', 
                         guild=guild, 
                         server_data=server_data,
                         user=session['user'])

@app.route('/api/server/<guild_id>/config', methods=['GET', 'POST'])
def server_config(guild_id):
    """API endpoint for server configuration"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if not user_has_permission(guild_id, session['user']['id']):
        return jsonify({'error': 'No permission'}), 403
    
    if request.method == 'GET':
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        server_data = loop.run_until_complete(get_server_data(guild_id))
        loop.close()
        return jsonify(server_data)
    
    elif request.method == 'POST':
        config_data = request.json
        
        # Update server configuration
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update_server_data(guild_id, config_data))
        loop.close()
        
        return jsonify({'success': True})

@app.route('/api/server/<guild_id>/logs')
def server_logs(guild_id):
    """Get server logs"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if not user_has_permission(guild_id, session['user']['id']):
        return jsonify({'error': 'No permission'}), 403
    
    try:
        # Get logs from global logging system
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if db:
            logs = loop.run_until_complete(
                db.global_logs.find({'guild_id': guild_id})
                .sort('timestamp', -1)
                .limit(100)
                .to_list(100)
            )
            # Convert ObjectId to string for JSON serialization
            for log in logs:
                log['_id'] = str(log['_id'])
                if 'timestamp' in log:
                    log['timestamp'] = log['timestamp'].isoformat()
        else:
            logs = []
        
        loop.close()
        return jsonify(logs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<guild_id>/stats')
def server_stats(guild_id):
    """Get server statistics"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if not user_has_permission(guild_id, session['user']['id']):
        return jsonify({'error': 'No permission'}), 403
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404
    
    # Calculate stats
    online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
    bot_count = sum(1 for member in guild.members if member.bot)
    human_count = guild.member_count - bot_count
    
    stats = {
        'member_count': guild.member_count,
        'online_members': online_members,
        'bot_count': bot_count,
        'human_count': human_count,
        'text_channels': len(guild.text_channels),
        'voice_channels': len(guild.voice_channels),
        'roles': len(guild.roles),
        'emojis': len(guild.emojis),
        'created_at': guild.created_at.isoformat(),
        'owner': {
            'name': guild.owner.display_name if guild.owner else 'Unknown',
            'id': guild.owner.id if guild.owner else None
        }
    }
    
    return jsonify(stats)

@app.route('/api/channels/<guild_id>')
def get_channels(guild_id):
    """Get server channels"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if not user_has_permission(guild_id, session['user']['id']):
        return jsonify({'error': 'No permission'}), 403
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404
    
    channels = []
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            channels.append({
                'id': channel.id,
                'name': channel.name,
                'type': 'text',
                'category': channel.category.name if channel.category else None
            })
        elif isinstance(channel, discord.VoiceChannel):
            channels.append({
                'id': channel.id,
                'name': channel.name,
                'type': 'voice',
                'category': channel.category.name if channel.category else None
            })
    
    return jsonify(channels)

@app.route('/api/roles/<guild_id>')
def get_roles(guild_id):
    """Get server roles"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if not user_has_permission(guild_id, session['user']['id']):
        return jsonify({'error': 'No permission'}), 403
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404
    
    roles = []
    for role in guild.roles:
        if role.name != '@everyone':
            roles.append({
                'id': role.id,
                'name': role.name,
                'color': str(role.color),
                'permissions': role.permissions.value,
                'mentionable': role.mentionable,
                'member_count': len(role.members)
            })
    
    return jsonify(roles)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
