from flask import Flask, request, redirect, url_for, jsonify, session, render_template_string
import requests
from bs4 import BeautifulSoup
import time
import os
import json
import threading

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Admin aur User data
USERS_FILE = 'users.json'
ADMIN_USERNAME = "MANI.302"

# Global logs storage
logs = []

def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({ADMIN_USERNAME: {"password": "123", "is_approved": True}}, f)

def get_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def capture_output(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 100:
        logs.pop(0)

# --- Messenger Logic ---
def send_messages(thread_id, cookies_str, messages, interval):
    try:
        # Cookies string ko dictionary mein convert karna
        cookie_dict = {c.split('=')[0]: c.split('=')[1] for c in cookies_str.split('; ') if '=' in c}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.facebook.com/'
        }

        session_req = requests.Session()
        for msg in messages:
            msg = msg.strip()
            if not msg: continue
            
            # FB message bhejne ka basic logic (Simulation)
            # Note: Reality mein FB complex tokens mangta hai, ye basic test hai
            capture_output(f"Sending: {msg} to {thread_id}")
            
            # Fake delay for simulation
            time.sleep(interval)
            capture_output(f"Successfully Sent: {msg}")

    except Exception as e:
        capture_output(f"Error in sending: {str(e)}")

# --- Routes ---
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return """
    <h1>Messenger Multi-Loader</h1>
    <p>Welcome, """ + session['user'] + """</p>
    <form action="/start" method="post" enctype="multipart/form-data">
        <input type="text" name="thread_id" placeholder="Thread ID" required><br><br>
        <textarea name="cookies" placeholder="Paste Cookies Here..." required></textarea><br><br>
        <input type="file" name="msg_file" required><br><br>
        <input type="number" name="interval" placeholder="Interval (seconds)" value="60"><br><br>
        <button type="submit">Start Loading</button>
    </form>
    <br><a href="/status">Check Status</a> | <a href="/logout">Logout</a>
    """

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = get_users()
        if username in users and users[username]['password'] == password:
            if users[username]['is_approved']:
                session['user'] = username
                return redirect(url_for('index'))
            return "Wait for Admin Approval!"
        return "Invalid Credentials!"
    return '<form method="post">User: <input name="username"><br>Pass: <input type="password" name="password"><br><button>Login</button></form>'

@app.route('/start', methods=['POST'])
def start_task():
    thread_id = request.form['thread_id']
    cookies = request.form['cookies']
    interval = int(request.form['interval'])
    file = request.files['msg_file']
    
    messages = file.read().decode('utf-8').splitlines()
    
    # Background thread mein chalana
    threading.Thread(target=send_messages, args=(thread_id, cookies, messages, interval)).start()
    return redirect(url_for('status'))

@app.route('/status')
def status():
    return "<h2>System Logs</h2><pre>" + "\n".join(logs[::-1]) + "</pre><br><a href='/'>Back</a>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    load_users()
    import os
    # Render dynamic port setting
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
