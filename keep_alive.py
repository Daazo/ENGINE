from flask import Flask, redirect
from threading import Thread
import time

app = Flask(__name__)

@app.route('/')
def home():
    # Redirect to dashboard
    return redirect('/dashboard', code=302)

@app.route('/dashboard')
def dashboard_redirect():
    return '''
    <html>
        <head>
            <title>VAAZHA Bot - Redirecting to Dashboard</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    text-align: center; 
                    background: #2f3136; 
                    color: white; 
                    padding: 50px; 
                }
                .status { 
                    background: #5865F2; 
                    padding: 30px; 
                    border-radius: 15px; 
                    display: inline-block; 
                    margin: 20px; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                }
                .emoji { font-size: 60px; margin-bottom: 20px; }
                .btn {
                    background: #43b581;
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 10px;
                    display: inline-block;
                    margin: 10px;
                    font-size: 18px;
                    transition: all 0.3s ease;
                }
                .btn:hover {
                    background: #369870;
                    transform: translateY(-2px);
                }
            </style>
        </head>
        <body>
            <div class="emoji">🌴</div>
            <h1>VAAZHA Bot Dashboard</h1>
            <div class="status">
                <h2>✅ Bot Status: Online & Ready!</h2>
                <p>Your Discord bot is running and the dashboard is active.</p>
                <p>Access the full dashboard to manage your servers:</p>
                <a href="http://localhost:5000" class="btn">🚀 Open Dashboard</a>
                <br><br>
                <p style="font-size: 14px; color: #99AAB5;">
                    Dashboard running on port 5000 • Made with ❤️ by Daazo
                </p>
            </div>
        </body>
    </html>
    '''

@app.route('/ping')
def ping():
    return "Bot is alive! Dashboard available on port 5000 🌴"

@app.route('/status')
def status():
    return {
        "status": "online",
        "bot": "VAAZHA Bot",
        "dashboard": "http://localhost:5000",
        "message": "Bot and dashboard running successfully! 🌴"
    }

def run():
    """Run Flask server"""
    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False)

def keep_alive():
    """Start the Flask server in a separate thread"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("🌴 Keep-alive server started on port 3000")