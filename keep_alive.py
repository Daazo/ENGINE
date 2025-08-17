
from flask import Flask
from threading import Thread
import time

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <html>
        <head>
            <title>VAAZHA Bot Status</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    text-align: center; 
                    background: #2f3136; 
                    color: white; 
                    padding: 50px; 
                }
                .status { 
                    background: #43b581; 
                    padding: 20px; 
                    border-radius: 10px; 
                    display: inline-block; 
                    margin: 20px; 
                }
                .emoji { font-size: 50px; }
            </style>
        </head>
        <body>
            <div class="emoji">🌴</div>
            <h1>VAAZHA Bot is Online!</h1>
            <div class="status">
                <h2>✅ Bot Status: Running</h2>
                <p>Your Discord bot is currently active and serving servers.</p>
                <p>Made with ❤️ by Daazo from God's Own Country</p>
            </div>
        </body>
    </html>
    '''

@app.route('/ping')
def ping():
    return "Bot is alive! 🌴"

@app.route('/status')
def status():
    return {
        "status": "online",
        "bot": "VAAZHA Bot",
        "message": "Bot is running successfully! 🌴"
    }

def run():
    """Run Flask server"""
    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False)reloader=False)

def keep_alive():
    """Start the Flask server in a separate thread"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("🌐 Keep-alive server started on port 5000")
