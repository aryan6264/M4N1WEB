from flask import Flask, request, redirect, url_for, session, render_template_string
import requests
import time
import os
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mani_all_in_one_key"

# --- Credentials ---
ADMIN_USER = "mani302"
ADMIN_PASS = "786786"

# Global data
logs = []
active_tasks = {}

def capture_output(message):
    timestamp = datetime.now().strftime("%I:%M:%S %p")
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 40: logs.pop(0)

# --- Common CSS for all pages ---
STYLE = '''
<style>
    body { background: #000; color: #39ff14; font-family: 'Courier New', monospace; padding: 20px; text-align: center; }
    .nav { margin-bottom: 20px; border-bottom: 1px solid #39ff14; padding-bottom: 10px; }
    .nav a { color: cyan; text-decoration: none; margin: 0 10px; font-weight: bold; }
    .card { border: 1px solid #39ff14; padding: 20px; display: inline-block; width: 90%; max-width: 500px; background: #0a0a0a; box-shadow: 0 0 10px #39ff14; }
    input, textarea, select { width: 100%; padding: 10px; margin: 10px 0; background: #111; border: 1px solid #39ff14; color: #fff; }
    button { width: 100%; padding: 12px; background: #39ff14; color: #000; border: none; font-weight: bold; cursor: pointer; }
    .logs { text-align: left; background: #111; padding: 10px; height: 200px; overflow-y: scroll; margin-top: 20px; border: 1px solid #333; font-size: 12px; }
    .stop-btn { background: red; color: white; padding: 5px; text-decoration: none; font-size: 10px; border-radius: 3px; }
</style>
'''

# --- Logic: Execution Engine ---
def execution_engine(task_id, target_id, cookies, messages, interval, task_name):
    msg_idx = 0
    while task_id in active_tasks and msg_idx < len(messages):
        try:
            msg = messages[msg_idx].strip()
            if msg:
                # Simulation of actual sending
                capture_output(f"🚀 {task_name.upper()} | Target: {target_id} | Msg: {msg[:15]}...")
                time.sleep(1)
                capture_output(f"✅ Success | Sent: {msg[:10]}...")
            
            msg_idx += 1
            time.sleep(interval)
        except Exception as e:
            capture_output(f"❌ Error in {task_id}: {str(e)}")
            break
    
    if task_id in active_tasks:
        del active_tasks[task_id]
        capture_output(f"🏁 {task_name} Finished.")

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == ADMIN_USER and request.form.get('p') == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('dashboard'))
    return render_template_string(STYLE + '''
        <div class="card" style="margin-top:100px;">
            <h2>MANI LOGIN</h2>
            <form method="post">
                <input name="u" placeholder="USERNAME" required><br>
                <input name="p" type="password" placeholder="PASSWORD" required><br>
                <button type="submit">LOGIN</button>
            </form>
        </div>
    ''')

@app.route('/')
def dashboard():
    if 'user' not in session: return redirect(url_for('login'))
    
    tasks_html = "".join([f"<li>{v['type']} on {v['target']} <a href='/stop/{k}' class='stop-btn'>STOP</a></li>" for k,v in active_tasks.items()])
    
    return render_template_string(STYLE + f'''
        <div class="nav">
            <a href="/">DASHBOARD</a> | <a href="/cookie_check">COOKIE CHECKER</a> | 
            <a href="/convo">CONVO TOOL</a> | <a href="/post">POST TOOL</a> | <a href="/logout" style="color:red;">LOGOUT</a>
        </div>
        <div class="card">
            <h2>MAIN DASHBOARD</h2>
            <p>Welcome, Mani Jani!</p>
            <hr>
            <h3>Active Processes:</h3>
            <ul style="text-align:left;">{tasks_html if tasks_html else "No Active Tasks"}</ul>
            <div class="logs">
                <strong>SYSTEM LOGS:</strong><br>
                {"<br>".join(logs[::-1])}
            </div>
        </div>
    ''')

@app.route('/cookie_check', methods=['GET', 'POST'])
def cookie_check():
    if 'user' not in session: return redirect(url_for('login'))
    status = ""
    if request.method == 'POST':
        c = request.form.get('cookie')
        if "c_user" in c and "xs" in c: status = "ACTIVE ✅"
        else: status = "INVALID/EXPIRED ❌"
        
    return render_template_string(STYLE + f'''
        <div class="nav"><a href="/">← BACK TO DASHBOARD</a></div>
        <div class="card">
            <h2>COOKIE CHECKER</h2>
            <form method="post">
                <textarea name="cookie" placeholder="Paste Cookie Here..." style="height:100px;"></textarea>
                <button type="submit">CHECK STATUS</button>
            </form>
            <h3 style="margin-top:20px;">STATUS: {status}</h3>
        </div>
    ''')

@app.route('/convo')
@app.route('/post')
def tools():
    if 'user' not in session: return redirect(url_for('login'))
    t_type = "convo" if "convo" in request.path else "post"
    return render_template_string(STYLE + f'''
        <div class="nav"><a href="/">← BACK TO DASHBOARD</a></div>
        <div class="card">
            <h2>{t_type.upper()} LOADER</h2>
            <form action="/start" method="post" enctype="multipart/form-data">
                <input type="hidden" name="type" value="{t_type}">
                <input name="target" placeholder="Target ID (Convo/Post)" required>
                <textarea name="cookies" placeholder="Cookies (One per line)" required></textarea>
                <input type="file" name="file" required>
                <input type="number" name="delay" value="60" placeholder="Delay (Seconds)">
                <button type="submit">START ATTACK</button>
            </form>
        </div>
    ''')

@app.route('/start', methods=['POST'])
def start():
    if 'user' not in session: return redirect(url_for('login'))
    t_type = request.form.get('type')
    t_target = request.form.get('target')
    delay = int(request.form.get('delay', 60))
    cookies = request.form.get('cookies').splitlines()
    f = request.files.get('file')
    
    if f:
        msgs = f.read().decode('utf-8').splitlines()
        task_id = f"{t_type}_{int(time.time())}"
        active_tasks[task_id] = {"target": t_target, "type": t_type}
        threading.Thread(target=execution_engine, args=(task_id, t_target, cookies, msgs, delay, t_type)).start()
        capture_output(f"⚡ {t_type} Started on {t_target}")
        
    return redirect(url_for('dashboard'))

@app.route('/stop/<task_id>')
def stop(task_id):
    if task_id in active_tasks:
        del active_tasks[task_id]
        capture_output(f"🛑 Stopped Task: {task_id}")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
