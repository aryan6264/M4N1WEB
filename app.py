from flask import Flask, request, redirect, url_for, session, render_template_string
import requests
import time
import os
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mani_neon_power_786"

# --- Credentials ---
ADMIN_USER = "mani302"
ADMIN_PASS = "786786"

# Global storage
logs = []
stop_events = {}

def capture_output(message):
    timestamp = datetime.now().strftime("%I:%M:%S %p")
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 60: logs.pop(0)

# --- Multi-Cookie Task Engine ---
def execution_engine(task_id, target_id, cookie_list, messages, interval):
    cookie_index = 0
    msg_index = 0
    
    while msg_index < len(messages) and task_id in stop_events:
        try:
            current_cookie = cookie_list[cookie_index].strip()
            cookie_dict = {c.split('=')[0]: c.split('=')[1] for c in current_cookie.split('; ') if '=' in c}
            
            msg = messages[msg_index].strip()
            if not msg: 
                msg_index += 1
                continue

            # Simulation of FB Request
            # Reality mein yahan requests.post ayega
            capture_output(f"🚀 Using ID {cookie_index + 1} | Target: {target_id}")
            capture_output(f"💌 Msg: {msg}")
            
            time.sleep(1)
            capture_output(f"✅ Success | Sent from Cookie {cookie_index + 1}")
            
            msg_index += 1
            time.sleep(interval)

        except Exception as e:
            capture_output(f"⚠️ Cookie {cookie_index + 1} Failed! Switching...")
            cookie_index = (cookie_index + 1) % len(cookie_list)
            time.sleep(2)

    capture_output(f"🏁 Task {task_id} Completed!")

# --- Neon UI Design ---
NEON_UI = '''
<!DOCTYPE html>
<html>
<head>
    <title>MANI CYBER LOADER</title>
    <style>
        body { background-color: #0a0a0a; color: #39ff14; font-family: 'Courier New', monospace; overflow-x: hidden; }
        .matrix-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; opacity: 0.1; }
        .container { max-width: 800px; margin: auto; padding: 20px; border: 2px solid #39ff14; box-shadow: 0 0 15px #39ff14; background: rgba(0,0,0,0.8); }
        h1 { text-align: center; text-shadow: 0 0 10px #39ff14; letter-spacing: 5px; }
        input, textarea, select { width: 100%; padding: 10px; margin: 10px 0; background: #111; border: 1px solid #39ff14; color: #fff; border-radius: 5px; }
        button { width: 100%; padding: 15px; background: #39ff14; color: #000; border: none; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:hover { box-shadow: 0 0 20px #39ff14; transform: scale(1.02); }
        .log-box { background: #000; border: 1px solid #333; height: 300px; overflow-y: scroll; padding: 10px; margin-top: 20px; font-size: 12px; }
        .footer { text-align: center; margin-top: 20px; font-size: 10px; color: #555; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MANI BRAND LOADER</h1>
        <p style="text-align:center;">SERVER TIME: {{ time }}</p>
        
        <form action="/start" method="post" enctype="multipart/form-data">
            <label>TARGET SETTING:</label>
            <input name="target_id" placeholder="Enter Target ID / Link" required>
            
            <label>MULTI-COOKIES (One per line):</label>
            <textarea name="cookies" placeholder="Paste multiple cookies here... Every cookie on a new line." style="height:100px;" required></textarea>
            
            <label>MESSAGES FILE:</label>
            <input type="file" name="msg_file" required>
            
            <label>SPEED (SECONDS):</label>
            <input type="number" name="interval" value="60" min="1">
            
            <button type="submit">ACTIVATE HACK MODE</button>
        </form>

        <div class="log-box">
            <h3 style="color: cyan;">>_ ACTIVITY_LOGS:</h3>
            {% for log in logs %}
                <div>{{ log }}</div>
            {% endfor %}
        </div>
        
        <div style="margin-top:10px; text-align:center;">
            <a href="/logout" style="color:red; text-decoration:none;">[ TERMINATE SESSION ]</a>
        </div>
    </div>
    <div class="footer">MADE BY MANI.302 | POWERED BY NEON ENGINE</div>
</body>
</html>
'''

LOGIN_UI = '''
<body style="background:#000; color:#39ff14; font-family:monospace; text-align:center; padding-top:150px;">
    <h2 style="text-shadow: 0 0 10px #39ff14;">SECURE ACCESS REQUIRED</h2>
    <form method="post" style="display:inline-block; border:1px solid #39ff14; padding:20px; box-shadow:0 0 10px #39ff14;">
        <input name="u" placeholder="USERNAME" style="background:#000; color:#fff; border:1px solid #39ff14; padding:10px;"><br><br>
        <input name="p" type="password" placeholder="PASSWORD" style="background:#000; color:#fff; border:1px solid #39ff14; padding:10px;"><br><br>
        <button style="background:#39ff14; color:#000; border:none; padding:10px 20px; cursor:pointer; font-weight:bold;">LOGIN</button>
    </form>
</body>
'''

# --- Routes ---
@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template_string(NEON_UI, logs=logs[::-1], time=datetime.now().strftime("%I:%M:%S %p"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == ADMIN_USER and request.form.get('p') == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('index'))
        return "ACCESS DENIED! <a href='/login' style='color:red;'>RETRY</a>"
    return render_template_string(LOGIN_UI)

@app.route('/start', methods=['POST'])
def start():
    if 'user' not in session: return redirect(url_for('login'))
    
    target = request.form.get('target_id')
    cookie_list = request.form.get('cookies').splitlines()
    interval = int(request.form.get('interval', 60))
    file = request.files.get('msg_file')
    
    if file and cookie_list:
        messages = file.read().decode('utf-8').splitlines()
        task_id = str(time.time())
        stop_events[task_id] = True
        
        threading.Thread(target=execution_engine, args=(task_id, target, cookie_list, messages, interval)).start()
        capture_output(f"⚡ System Online. Multi-Cookie Mode Active ({len(cookie_list)} IDs).")

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
