
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import discord
from discord.ext import commands
import motor.motor_asyncio
import asyncio
import os
from datetime import datetime, timedelta
import json
from main import get_server_data, update_server_data, db, bot, MONGO_URI
import time

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'vaazha-dashboard-secret-key-2024')

# MongoDB connection for dashboard
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI) if MONGO_URI else None
dashboard_db = mongo_client.vaazha_bot if mongo_client else None

# Dashboard configuration
DASHBOARD_PORT = 8080

@app.route('/')
def dashboard_home():
    """Main dashboard page with overview"""
    try:
        # Get basic bot stats
        bot_stats = {
            'server_count': len(bot.guilds) if bot.guilds else 0,
            'total_members': sum(guild.member_count for guild in bot.guilds) if bot.guilds else 0,
            'uptime': str(timedelta(seconds=int(time.time() - bot.start_time))) if hasattr(bot, 'start_time') else 'Unknown',
            'status': 'Online' if bot.is_ready() else 'Offline'
        }
        
        # Get server list for dropdown
        servers = []
        if bot.guilds:
            for guild in bot.guilds:
                servers.append({
                    'id': guild.id,
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon': guild.icon.url if guild.icon else None
                })
        
        return render_template('dashboard.html', 
                             bot_stats=bot_stats, 
                             servers=servers,
                             selected_server=None)
    except Exception as e:
        return f"Dashboard Error: {str(e)}", 500

@app.route('/server/<int:server_id>')
def server_dashboard(server_id):
    """Server-specific dashboard"""
    try:
        guild = bot.get_guild(server_id)
        if not guild:
            return "Server not found", 404
        
        # Get server data from database
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        server_data = loop.run_until_complete(get_server_data(server_id))
        loop.close()
        
        # Get basic server stats
        server_stats = {
            'name': guild.name,
            'member_count': guild.member_count,
            'channel_count': len(guild.channels),
            'role_count': len(guild.roles),
            'owner': str(guild.owner),
            'created_at': guild.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'icon': guild.icon.url if guild.icon else None
        }
        
        # Get all servers for dropdown
        servers = []
        for g in bot.guilds:
            servers.append({
                'id': g.id,
                'name': g.name,
                'member_count': g.member_count
            })
        
        return render_template('server_dashboard.html',
                             server_stats=server_stats,
                             server_data=server_data,
                             servers=servers,
                             selected_server=server_id,
                             channels=guild.channels,
                             roles=guild.roles)
    except Exception as e:
        return f"Server Dashboard Error: {str(e)}", 500

@app.route('/api/economy/<int:server_id>')
def api_economy_stats(server_id):
    """API endpoint for economy statistics"""
    try:
        if not dashboard_db:
            return jsonify({'error': 'Database not connected'}), 500
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get economy stats
        total_users = loop.run_until_complete(
            dashboard_db.economy.count_documents({'guild_id': str(server_id)})
        )
        
        # Get top 10 richest users
        richest = loop.run_until_complete(
            dashboard_db.economy.find({'guild_id': str(server_id)})
            .sort([('coins', -1), ('bank', -1)])
            .limit(10)
            .to_list(None)
        )
        
        # Calculate total coins in circulation
        pipeline = [
            {'$match': {'guild_id': str(server_id)}},
            {'$group': {
                '_id': None,
                'total_coins': {'$sum': '$coins'},
                'total_bank': {'$sum': '$bank'},
                'total_earned': {'$sum': '$total_earned'},
                'total_spent': {'$sum': '$total_spent'}
            }}
        ]
        circulation = loop.run_until_complete(
            dashboard_db.economy.aggregate(pipeline).to_list(None)
        )
        
        loop.close()
        
        # Format richest users
        richest_formatted = []
        guild = bot.get_guild(server_id)
        for user_data in richest:
            user = guild.get_member(int(user_data['user_id'])) if guild else None
            if user:
                richest_formatted.append({
                    'name': user.display_name,
                    'avatar': user.display_avatar.url,
                    'total_wealth': user_data.get('coins', 0) + user_data.get('bank', 0),
                    'coins': user_data.get('coins', 0),
                    'bank': user_data.get('bank', 0)
                })
        
        circulation_data = circulation[0] if circulation else {
            'total_coins': 0, 'total_bank': 0, 'total_earned': 0, 'total_spent': 0
        }
        
        return jsonify({
            'total_users': total_users,
            'circulation': circulation_data,
            'richest': richest_formatted
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/karma/<int:server_id>')
def api_karma_stats(server_id):
    """API endpoint for karma statistics"""
    try:
        if not dashboard_db:
            return jsonify({'error': 'Database not connected'}), 500
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get karma stats
        total_users = loop.run_until_complete(
            dashboard_db.karma.count_documents({'guild_id': str(server_id)})
        )
        
        # Get top 10 karma holders
        top_karma = loop.run_until_complete(
            dashboard_db.karma.find({'guild_id': str(server_id)})
            .sort('karma', -1)
            .limit(10)
            .to_list(None)
        )
        
        # Calculate total karma distributed
        pipeline = [
            {'$match': {'guild_id': str(server_id)}},
            {'$group': {
                '_id': None,
                'total_karma': {'$sum': '$karma'},
                'avg_karma': {'$avg': '$karma'}
            }}
        ]
        karma_stats = loop.run_until_complete(
            dashboard_db.karma.aggregate(pipeline).to_list(None)
        )
        
        loop.close()
        
        # Format top karma users
        top_karma_formatted = []
        guild = bot.get_guild(server_id)
        for user_data in top_karma:
            user = guild.get_member(int(user_data['user_id'])) if guild else None
            if user:
                top_karma_formatted.append({
                    'name': user.display_name,
                    'avatar': user.display_avatar.url,
                    'karma': user_data.get('karma', 0)
                })
        
        karma_data = karma_stats[0] if karma_stats else {
            'total_karma': 0, 'avg_karma': 0
        }
        
        return jsonify({
            'total_users': total_users,
            'stats': karma_data,
            'top_karma': top_karma_formatted
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<int:server_id>/config', methods=['GET', 'POST'])
def api_server_config(server_id):
    """API endpoint for server configuration"""
    try:
        if request.method == 'GET':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            server_data = loop.run_until_complete(get_server_data(server_id))
            loop.close()
            return jsonify(server_data)
        
        elif request.method == 'POST':
            config_data = request.json
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(update_server_data(server_id, config_data))
            loop.close()
            return jsonify({'success': True, 'message': 'Configuration updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/stats')
def api_bot_stats():
    """API endpoint for bot statistics"""
    try:
        stats = {
            'server_count': len(bot.guilds) if bot.guilds else 0,
            'total_members': sum(guild.member_count for guild in bot.guilds) if bot.guilds else 0,
            'uptime': str(timedelta(seconds=int(time.time() - bot.start_time))) if hasattr(bot, 'start_time') else 'Unknown',
            'status': 'Online' if bot.is_ready() else 'Offline',
            'latency': round(bot.latency * 1000, 2) if hasattr(bot, 'latency') else 0
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_dashboard():
    """Run the Flask dashboard"""
    print(f"🌐 Starting VAAZHA Bot Dashboard on port {DASHBOARD_PORT}")
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False)

if __name__ == '__main__':
    run_dashboard()
