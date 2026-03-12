from flask import Flask, request, redirect, url_for, session, render_template_string
import requests
import re
import time
import os
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mani_mobile_v5_extractor"

ADMIN_USER = "mani302"
ADMIN_PASS = "786786"

logs = []
active_tasks = {}

def capture_output(message):
    timestamp = datetime.now().strftime("%I:%M:%S")
    logs.append(f"[{timestamp}] {message}")
    if len(logs) > 30: logs.pop(0)

# --- Mobile UI CSS ---
MOBILE_STYLE = '''
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #050505; color: #39ff14; font-family: 'Segoe UI', sans-serif; padding-bottom: 80px; }
    .header { background: #111; padding: 15px; text-align: center; border-bottom: 1px solid #39ff14; position: sticky; top: 0; z-index: 100; }
    .header h2 { font-size: 1.2rem; text-shadow: 0 0 10px #39ff14; }
    .container { padding: 15px; }
    .card { background: #111; border-radius: 10px; padding: 15px; margin-bottom: 15px; border: 0.5px solid #333; }
    input, textarea, select { width: 100%; padding: 12px; margin: 8px 0; background: #1a1a1a; border: 1px solid #39ff14; color: #fff; border-radius: 5px; }
    button { width: 100%; padding: 12px; background: #39ff14; color: #000; border: none; font-weight: bold; border-radius: 5px; margin-top: 10px; box-shadow: 0 0 10px #39ff14; }
    .nav-bar { position: fixed; bottom: 0; left: 0; width: 100%; background: #111; display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid #39ff14; z-index: 1000; }
    .nav-item { color: #fff; text-decoration: none; font-size: 10px; text-align: center; opacity: 0.6; }
    .nav-item.active { color: #39ff14; opacity: 1; font-weight: bold; }
    .nav-icon { font-size: 18px; display: block; margin-bottom: 2px; }
    .id-list { background: #000; padding: 10px; border: 1px dashed #39ff14; margin-top: 10px; text-align: left; font-size: 12px; }
</style>
'''

# --- Logic: Post Extractor ---
def extract_post_ids(profile_url, cookie):
    ids = []
    try:
        # Convert to mbasic
        mbasic_url = profile_url.replace("www.facebook.com", "mbasic.facebook.com")
        headers = {'Cookie': cookie, 'User-Agent': 'Mozilla/5.0'}
        response = requests.get(mbasic_url, headers=headers)
        
        # Simple Regex to find post IDs in mbasic links
        # This looks for numeric IDs in /story.php or /posts/
        matches = re.findall(r'id=(\d+)', response.text) or re.findall(r'posts/(\d+)', response.text)
        
        # Remove duplicates and take first 5
        seen = set()
        for m in matches:
            if m not in seen and len(m) > 10:
                ids.append(m)
                seen.add(m)
            if len(ids) >= 5: break
    except:
        pass
    return ids

# --- Routes ---

@app.route('/')
def dashboard():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template_string(MOBILE_STYLE + f'''
        <div class="header"><h2>MANI DASHBOARD</h2></div>
        <div class="container">
            <div class="card"><h4>STATUS: SERVER ONLINE ⚡</h4></div>
            <div class="card" style="height:200px; overflow-y:auto;">
                <h4>SYSTEM LOGS</h4>
                <div style="font-size:11px; color:#0f0;">{"<br>".join(logs[::-1])}</div>
            </div>
        </div>
        <div class="nav-bar">
            <a href="/" class="nav-item active"><span class="nav-icon">🏠</span>Home</a>
            <a href="/extractor" class="nav-item"><span class="nav-icon">🔍</span>Extract</a>
            <a href="/convo" class="nav-item"><span class="nav-icon">💬</span>Convo</a>
            <a href="/post" class="nav-item"><span class="nav-icon">📝</span>Post</a>
        </div>
    ''')

@app.route('/extractor', methods=['GET', 'POST'])
def extractor():
    if 'user' not in session: return redirect(url_for('login'))
    found_ids = []
    if request.method == 'POST':
        url = request.form.get('profile_url')
        cookie = request.form.get('cookie')
        found_ids = extract_post_ids(url, cookie)
        capture_output(f"Extracted {len(found_ids)} IDs from profile.")

    return render_template_string(MOBILE_STYLE + f'''
        <div class="header"><h2>ID EXTRACTOR</h2></div>
        <div class="container">
            <div class="card">
                <form method="post">
                    <input name="profile_url" placeholder="Paste Profile Link" required>
                    <textarea name="cookie" placeholder="Your Cookie (Required to scan)" style="height:60px;" required></textarea>
                    <button type="submit">GET RECENT 5 POST IDs</button>
                </form>
                { f'<div class="id-list"><strong>Found IDs:</strong><br>' + "<br>".join(found_ids) + '</div>' if found_ids else '' }
                <p style="font-size:10px; margin-top:10px; color:#888;">Note: Profile must be public or your friend.</p>
            </div>
        </div>
        <div class="nav-bar">
            <a href="/" class="nav-item"><span class="nav-icon">🏠</span>Home</a>
            <a href="/extractor" class="nav-item active"><span class="nav-icon">🔍</span>Extract</a>
            <a href="/convo" class="nav-item"><span class="nav-icon">💬</span>Convo</a>
            <a href="/post" class="nav-item"><span class="nav-icon">📝</span>Post</a>
        </div>
    ''')

# --- Login, Convo, Post (Same as before) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == ADMIN_USER and request.form.get('p') == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('dashboard'))
    return render_template_string(MOBILE_STYLE + '<div style="padding:50px 20px;"><div class="card"><h2>LOGIN</h2><form method="post"><input name="u" placeholder="USER"><input name="p" type="password" placeholder="PASS"><button>ENTER</button></form></div></div>')

@app.route('/convo')
@app.route('/post')
def tools():
    if 'user' not in session: return redirect(url_for('login'))
    t_type = "convo" if "convo" in request.path else "post"
    return render_template_string(MOBILE_STYLE + f'''
        <div class="header"><h2>{t_type.upper()} LOADER</h2></div>
        <div class="container">
            <div class="card">
                <form action="/start" method="post" enctype="multipart/form-data">
                    <input type="hidden" name="type" value="{t_type}">
                    <input name="target" placeholder="Target ID" required>
                    <textarea name="cookies" placeholder="Cookies" required></textarea>
                    <input type="file" name="file" required>
                    <input type="number" name="delay" value="60">
                    <button type="submit">START</button>
                </form>
            </div>
        </div>
        <div class="nav-bar"><a href="/" class="nav-item">🏠</a><a href="/extractor" class="nav-item">🔍</a></div>
    ''')

# (Iske baad baki routes Start/Stop/Logout same purane wale hi add kar lena niche)
@app.route('/start', methods=['POST'])
def start():
    t_type = request.form.get('type'); t_target = request.form.get('target')
    delay = int(request.form.get('delay', 60)); cookies = request.form.get('cookies').splitlines()
    f = request.files.get('file')
    if f:
        msgs = f.read().decode('utf-8').splitlines(); task_id = f"{t_type}_{int(time.time())}"
        active_tasks[task_id] = {"target": t_target, "type": t_type}
        # Threading logic...
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
