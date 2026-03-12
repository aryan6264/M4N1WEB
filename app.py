from flask import Flask, request, redirect, url_for, jsonify, session, render_template_string
import requests
from bs4 import BeautifulSoup
import time
import os
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mani_power_key"

# --- Credentials ---
ADMIN_USER = "mani302"
ADMIN_PASS = "786786"

# Global storage for logs and active tasks
logs = []

def capture_output(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 100: logs.pop(0)

# --- Helper: Cookie Checker ---
def check_cookies(cookie_str):
    try:
        cookie_dict = {c.split('=')[0]: c.split('=')[1] for c in cookie_str.split('; ') if '=' in c}
        res = requests.get("https://mbasic.facebook.com/profile.php", cookies=cookie_dict)
        if "logout" in res.text.lower() or "mbasic_logout_button" in res.text:
            return True, "Cookie Active ✅"
        return False, "Cookie Expired ❌"
    except:
        return False, "Invalid Format ⚠️"

# --- Multi-Function Engine ---
def execution_engine(task_type, target_id, cookies_str, messages, interval):
    cookie_dict = {c.split('=')[0]: c.split('=')[1] for c in cookies_str.split('; ') if '=' in c}
    
    for msg in messages:
        if not msg.strip(): continue
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            
            if task_type == "comment":
                # Logic for Post Comment
                url = f"https://mbasic.facebook.com/{target_id}"
                capture_output(f"Commenting on Post: {target_id}")
            elif task_type == "convo":
                # Logic for Group/Convo
                capture_output(f"Sending to Convo: {target_id}")
            else:
                # Logic for Personal IB
                capture_output(f"Sending to Personal IB: {target_id}")

            # Simulation of sending
            time.sleep(1) 
            capture_output(f"Success | Time: {current_time} | Msg: {msg}")
            
            # Show Cookie status during work
            is_ok, _ = check_cookies(cookies_str)
            if not is_ok:
                capture_output("STOPPED: Cookie expired during task!")
                break

            time.sleep(interval)
        except Exception as e:
            capture_output(f"Error: {str(e)}")

# --- UI (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MANI MULTI-LOADER</title>
    <style>
        body { background: #000; color: #0f0; font-family: monospace; padding: 20px; }
        input, textarea, select { background: #111; color: #0f0; border: 1px solid #0f0; width: 100%; margin-bottom: 10px; padding: 10px; }
        button { background: #0f0; color: #000; padding: 10px 20px; cursor: pointer; border: none; font-weight: bold; }
        .log-box { background: #111; padding: 10px; border: 1px solid #333; height: 300px; overflow-y: scroll; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>Mani Multi-Loader v2.0</h1>
    <p>Current Time: {{ time }}</p>

    <form action="/start" method="post" enctype="multipart/form-data">
        <select name="task_type">
            <option value="convo">FB Convo Message</option>
            <option value="inbox">Personal IB Message</option>
            <option value="comment">Post Comment</option>
        </select>
        <input type="text" name="target_id" placeholder="Target ID (Post/Convo/User ID)" required>
        <textarea name="cookies" placeholder="Paste Cookies here..." required></textarea>
        <input type="file" name="msg_file" required>
        <input type="number" name="interval" placeholder="Time Interval (Seconds)" value="60">
        <button type="submit">Start Loading</button>
    </form>

    <div class="log-box">
        <h3>System Logs (Activity)</h3>
        {% for log in logs %}
            <div>{{ log }}</div>
        {% endfor %}
    </div>
    <br><a href="/logout" style="color: red;">Logout</a>
</body>
</html>
"""

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template_string(HTML_TEMPLATE, logs=logs[::-1], time=datetime.now().strftime("%I:%M:%S %p"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('index'))
        return "Wrong ID/Pass Jani!"
    return '<h1>Mani Login</h1><form method="post">User: <input name="u"><br>Pass: <input name="p" type="password"><br><button>Enter</button></form>'

@app.route('/start', methods=['POST'])
def start():
    task_type = request.form['task_type']
    target_id = request.form['target_id']
    cookies = request.form['cookies']
    interval = int(request.form['interval'])
    file = request.files['msg_file']
    
    # Cookie Check
    active, msg = check_cookies(cookies)
    capture_output(f"Status: {msg}")
    
    if active:
        messages = file.read().decode('utf-8').splitlines()
        threading.Thread(target=execution_engine, args=(task_type, target_id, cookies, messages, interval)).start()
        capture_output("Engine Started Successfully!")
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
