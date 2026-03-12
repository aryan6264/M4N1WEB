from flask import Flask, request, render_template_string, redirect, url_for, make_response, jsonify
import requests
import re
from threading import Thread, Event, Lock
import time
import random
import string
import uuid
import datetime
import os

app = Flask(__name__)

# ======================= GLOBAL VARIABLES =======================

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; TECNO CE7j) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.40 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'https://mbasic.facebook.com/'
}

stop_events = {}
pause_events = {}
threads = {}
task_status = {}
task_owners = {}
MAX_THREADS = 10
active_threads = 0

pending_approvals = {}
approved_keys = {}

# Admin Secret Key
ADMIN_SECRET_KEY = 'daku302' 

# ======================= COOKIE DELIVERY UTILS =======================

def get_fb_tokens(session, thread_id):
    """Bypasses security by fetching fb_dtsg and jazoest from mbasic"""
    try:
        url = f'https://mbasic.facebook.com/messages/read/?tid={thread_id}'
        res = session.get(url, headers=headers)
        fb_dtsg = re.search(r'name="fb_dtsg" value="(.*?)"', res.text).group(1)
        jazoest = re.search(r'name="jazoest" value="(.*?)"', res.text).group(1)
        tids = re.search(r'name="tids" value="(.*?)"', res.text).group(1)
        www_base_domain = re.search(r'name="www_base_domain" value="(.*?)"', res.text).group(1)
        return {'fb_dtsg': fb_dtsg, 'jazoest': jazoest, 'tids': tids, 'www_base_domain': www_base_domain}
    except:
        return None

def send_messages(cookies, thread_id, hater_name, time_interval, messages, task_id):
    global active_threads
    active_threads += 1
    task_status[task_id] = {
        "running": True, 
        "paused": False, 
        "sent": 0, 
        "failed": 0, 
        "tokens_info": {}, 
        "total_to_send": len(messages) * len(cookies)
    }
    
    # Initialize Cookie Info
    for cookie in cookies:
        task_status[task_id]["tokens_info"][cookie] = {
            "name": f"User_{cookie[-5:]}", # Masked ID
            "valid": True,
            "sent_count": 0,
            "failed_count": 0
        }

    try:
        msg_idx = 0
        while not stop_events[task_id].is_set():
            if pause_events[task_id].is_set():
                task_status[task_id]["paused"] = True
                time.sleep(1)
                continue
            
            task_status[task_id]["paused"] = False

            for cookie in cookies:
                if stop_events[task_id].is_set() or pause_events[task_id].is_set():
                    break
                
                try:
                    session = requests.Session()
                    # Convert string cookie to dict
                    c_dict = {c.split('=')[0]: c.split('=')[1] for c in cookie.split('; ') if '=' in c}
                    session.cookies.update(c_dict)

                    # Get required hidden tokens for this thread
                    fb_data = get_fb_tokens(session, thread_id)
                    
                    if fb_data:
                        message = f"{hater_name} {messages[msg_idx % len(messages)]}"
                        payload = {
                            'fb_dtsg': fb_data['fb_dtsg'],
                            'jazoest': fb_data['jazoest'],
                            'body': message,
                            'send': 'Send',
                            'tids': fb_data['tids'],
                            'www_base_domain': fb_data['www_base_domain']
                        }
                        
                        # Use mbasic send endpoint for highest delivery
                        post_url = 'https://mbasic.facebook.com/messages/send/'
                        response = session.post(post_url, data=payload, headers=headers)
                        
                        if response.status_code == 200:
                            task_status[task_id]["sent"] += 1
                            task_status[task_id]["tokens_info"][cookie]["sent_count"] += 1
                        else:
                            task_status[task_id]["failed"] += 1
                    else:
                        task_status[task_id]["failed"] += 1
                        task_status[task_id]["tokens_info"][cookie]["valid"] = False

                except Exception:
                    task_status[task_id]["failed"] += 1
                
                msg_idx += 1
                time.sleep(time_interval)
                
    finally:
        active_threads -= 1
        task_status[task_id]["running"] = False

# ======================= ROUTES =======================

@app.route('/')
def index():
    theme = request.cookies.get('theme', 'dark')
    is_admin = request.cookies.get('is_admin') == 'true'
    return render_template_string(TEMPLATE, section=None, theme=theme, is_admin=is_admin)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_SECRET_KEY:
            response = make_response(redirect(url_for('index')))
            response.set_cookie('is_admin', 'true')
            return response
    return 'Admin Login: <form method="POST"><input type="password" name="password"><button>Login</button></form>'

@app.route('/section/1', methods=['GET', 'POST'])
def section1():
    theme = request.cookies.get('theme', 'dark')
    is_admin = request.cookies.get('is_admin') == 'true'
    result = None
    
    if request.method == 'POST':
        # Handling Key Approval
        provided_key = request.form.get('key')
        if provided_key in approved_keys or provided_key == "MANI-BOSS": # Bypass for owner
            # Get Cookies
            if request.form.get('tokenOption') == 'single':
                cookies = [request.form.get('singleToken')]
            else:
                f = request.files.get('tokenFile')
                cookies = f.read().decode().splitlines()
            
            thread_id = request.form.get('threadId').replace('t_', '')
            hater_name = request.form.get('kidx')
            interval = int(request.form.get('time'))
            msg_file = request.files.get('txtFile')
            messages = msg_file.read().decode().splitlines()
            
            task_id = str(uuid.uuid4())
            stop_events[task_id] = Event()
            pause_events[task_id] = Event()
            
            Thread(target=send_messages, args=(cookies, thread_id, hater_name, interval, messages, task_id)).start()
            result = f"🟢 Task Started! ID: {task_id}"
        else:
            new_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            pending_approvals[new_key] = "pending"
            result = f"❌ Key Unapproved. Send this to WhatsApp: {new_key}"

    return render_template_string(TEMPLATE, section='1', theme=theme, is_admin=is_admin, result=result)

@app.route('/status')
def status():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin: return redirect(url_for('index'))
    return render_template_string(STATUS_TEMPLATE, task_status=task_status)

@app.route('/stop_task')
def stop_task():
    tid = request.args.get('stopTaskId')
    if tid in stop_events:
        stop_events[tid].set()
    return redirect(url_for('index'))

# ======================= TEMPLATE (MOBILE NEON UI) =======================

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>DAKU 302 COOKIE SERVER</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #000; color: #fff; font-family: 'Segoe UI', sans-serif; text-align: center; background-image: url('https://i.imgur.com/83p1Xb0.jpeg'); background-size: cover; }
    .container { max-width: 600px; margin-top: 20px; background: rgba(0,0,0,0.8); padding: 20px; border-radius: 15px; border: 2px solid #39ff14; box-shadow: 0 0 20px #39ff14; }
    h1 { color: #39ff14; text-shadow: 0 0 10px #39ff14; font-weight: bold; }
    .btn-submit { background: #39ff14; color: #000; font-weight: bold; width: 100%; margin-top: 15px; border: none; padding: 10px; }
    .form-control { background: #111; border: 1px solid #39ff14; color: #fff; margin-bottom: 10px; }
    .form-control:focus { background: #1a1a1a; color: #fff; border: 2px solid #39ff14; box-shadow: none; }
    .nav-box { margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .nav-box a { color: cyan; text-decoration: none; margin: 0 10px; font-weight: bold; }
  </style>
</head>
<body>
  <div class="container">
    <h1>𝗠𝗔𝗡𝗜 𝗥𝗔𝗝𝗣𝗨𝗧</h1>
    <p>✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐂𝐎𝐎𝐊𝐈𝐄  ▂▃▅▆▓▒░✩</p>
    
    <div class="nav-box">
        <a href="/">HOME</a> | <a href="/section/1">CONVO</a> | 
        {% if is_admin %}<a href="/status">SERVER STATUS</a>{% endif %}
    </div>

    {% if not section %}
        <div class="mt-4">
            <a href="/section/1" class="btn btn-outline-success w-100 mb-2">◄ 1 – COOKIE CONVO SERVER ►</a>
            <p>Select a tool from the menu to start</p>
        </div>
    {% elif section == '1' %}
        <form method="post" enctype="multipart/form-data">
            <select name="tokenOption" class="form-control" onchange="toggleC(this.value)">
                <option value="single">Single Cookie</option>
                <option value="file">Cookie File (.txt)</option>
            </select>
            <input type="text" name="singleToken" id="sC" class="form-control" placeholder="Paste Cookie Here">
            <input type="file" name="tokenFile" id="fC" class="form-control" style="display:none;">
            
            <input type="text" name="threadId" class="form-control" placeholder="Target Convo ID" required>
            <input type="text" name="kidx" class="form-control" placeholder="Hater Name" required>
            <input type="number" name="time" class="form-control" placeholder="Delay (Seconds)" required>
            <label>Message File:</label>
            <input type="file" name="txtFile" class="form-control" required>
            
            <input type="text" name="key" class="form-control" placeholder="Enter Approval Key" required>
            
            <button type="submit" class="btn-submit">LAUNCH COOKIE ATTACK</button>
        </form>
        
        <form action="/stop_task" method="get" class="mt-4">
            <input type="text" name="stopTaskId" class="form-control" placeholder="Task ID to Stop">
            <button type="submit" class="btn btn-danger w-100">STOP TASK</button>
        </form>
    {% endif %}

    {% if result %}<div class="alert alert-info mt-3" style="background:transparent; border:1px dashed #39ff14; color:#39ff14;">{{ result|safe }}</div>{% endif %}
  </div>

  <script>
    function toggleC(v) {
        document.getElementById('sC').style.display = v==='single'?'block':'none';
        document.getElementById('fC').style.display = v==='file'?'block':'none';
    }
  </script>
</body>
</html>
'''

STATUS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Server Status</title>
    <style>
        body { background: #000; color: #39ff14; font-family: monospace; padding: 20px; }
        .box { border: 1px solid #39ff14; padding: 15px; margin-bottom: 15px; }
        .green { color: lime; } .red { color: red; }
    </style>
</head>
<body>
    <h1>LIVE SERVER STATUS</h1>
    {% for tid, s in task_status.items() %}
    <div class="box">
        <h3>Task ID: {{ tid }}</h3>
        <p>Status: {{ "RUNNING" if s.running else "STOPPED" }}</p>
        <p>Sent: <span class="green">{{ s.sent }}</span> | Failed: <span class="red">{{ s.failed }}</span></p>
        <hr>
        {% for cookie, info in s.tokens_info.items() %}
            <div style="font-size: 12px;">Cookie: {{ info.name }} - Sent: {{ info.sent_count }}</div>
        {% endfor %}
    </div>
    {% endfor %}
    <a href="/" style="color:cyan;">Back to Home</a>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
