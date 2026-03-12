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
app.debug = True

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

proxy_lock = Lock()
proxy_list = []
proxy_index = 0

# Admin Secret Key
ADMIN_SECRET_KEY = 'daku302' 

# ======================= COOKIE DELIVERY ENGINE =======================

def get_fb_tokens(session, thread_id):
    """Bypasses security by fetching fb_dtsg and jazoest from mbasic"""
    try:
        # thread_id se 't_' hata kar numeric ID nikalna
        clean_id = thread_id.replace('t_', '')
        url = f'https://mbasic.facebook.com/messages/read/?tid={clean_id}'
        res = session.get(url, headers=headers)
        
        fb_dtsg = re.search(r'name="fb_dtsg" value="(.*?)"', res.text).group(1)
        jazoest = re.search(r'name="jazoest" value="(.*?)"', res.text).group(1)
        tids = re.search(r'name="tids" value="(.*?)"', res.text).group(1)
        www_base_domain = re.search(r'name="www_base_domain" value="(.*?)"', res.text).group(1)
        
        return {'fb_dtsg': fb_dtsg, 'jazoest': jazoest, 'tids': tids, 'www_base_domain': www_base_domain}
    except Exception as e:
        print(f"Token Error: {e}")
        return None

def send_messages(cookies, thread_id, mn, time_interval, messages, task_id):
    global active_threads
    active_threads += 1
    task_status[task_id] = {"running": True, "paused": False, "sent": 0, "failed": 0, "tokens_info": {}}
    
    for c in cookies:
        task_status[task_id]["tokens_info"][c] = {"name": f"User_{c[-5:]}", "valid": True, "sent_count": 0, "failed_count": 0}

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
                    # Cookie string handling
                    c_dict = {c.strip().split('=')[0]: c.strip().split('=')[1] for c in cookie.split(';') if '=' in c}
                    session.cookies.update(c_dict)

                    fb_data = get_fb_tokens(session, thread_id)
                    
                    if fb_data:
                        full_message = f"{mn} {messages[msg_idx % len(messages)]}"
                        payload = {
                            'fb_dtsg': fb_data['fb_dtsg'],
                            'jazoest': fb_data['jazoest'],
                            'body': full_message,
                            'send': 'Send',
                            'tids': fb_data['tids'],
                            'www_base_domain': fb_data['www_base_domain']
                        }
                        
                        response = session.post('https://mbasic.facebook.com/messages/send/', data=payload, headers=headers)
                        
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
            response.set_cookie('is_admin', 'true', max_age=60*60*24*365)
            return response
    return '<h1>Admin Access</h1><form method="post"><input type="password" name="password"><button>Login</button></form>'

@app.route('/section/<sec>', methods=['GET', 'POST'])
def section(sec):
    global pending_approvals
    result = None
    theme = request.cookies.get('theme', 'dark')
    is_admin = request.cookies.get('is_admin') == 'true'
    
    # Approval Logic
    is_approved = False
    approved_cookie = request.cookies.get('approved_key')
    if approved_cookie and approved_cookie in approved_keys:
        is_approved = True

    if sec == '1' and request.method == 'POST':
        provided_key = request.form.get('key')
        
        # Check if key is valid or already approved
        if provided_key in approved_keys or is_approved or provided_key == "MANI-BOSS":
            key_to_use = approved_cookie if is_approved else provided_key
            
            # Get Cookies from Input
            token_option = request.form.get('tokenOption')
            if token_option == 'single':
                cookies = [request.form.get('singleToken')]
            else:
                f = request.files.get('tokenFile')
                cookies = f.read().decode().splitlines()

            thread_id = request.form.get('threadId')
            mn = request.form.get('kidx')
            time_interval = int(request.form.get('time'))
            messages_file = request.files.get('txtFile')
            messages = messages_file.read().decode().splitlines()
            
            task_id = str(uuid.uuid4())
            stop_events[task_id] = Event()
            pause_events[task_id] = Event()
            task_owners[task_id] = key_to_use

            if active_threads >= MAX_THREADS:
                result = "❌ Server Busy! Stop other tasks first."
            else:
                t = Thread(target=send_messages, args=(cookies, thread_id, mn, time_interval, messages, task_id))
                t.start()
                result = f"🟢 Task Started! ID: {task_id}"
                
            response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=True, approved_key=key_to_use, theme=theme, is_admin=is_admin))
            response.set_cookie('approved_key', key_to_use, max_age=60*60*24*365)
            return response

        else:
            # Generate New Key if not approved
            new_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            pending_approvals[new_key] = "pending"
            result = f"❌ Key Unapproved. Send to Admin: {new_key}"
            return render_template_string(TEMPLATE, section=sec, result=result, is_approved=False, theme=theme, is_admin=is_admin)

    return render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme, is_admin=is_admin)

@app.route('/status')
def status_page():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin: return redirect(url_for('index'))
    return render_template_string(STATUS_TEMPLATE, task_status=task_status)

@app.route('/stop_task', methods=['GET'])
def stop_task():
    task_id = request.args.get('stopTaskId')
    if task_id in stop_events:
        stop_events[task_id].set()
    return redirect(url_for('index'))

# ======================= NEON TEMPLATE =======================

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐒𝐄𝐑𝐕𝐄𝐑  ▂▃▅▆▓▒░✩</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #000; color: #fff; font-family: 'Times New Roman', serif; text-align: center; background-image: url('https://i.imgur.com/83p1Xb0.jpeg'); background-size: cover; background-attachment: fixed; }
    .container { max-width: 700px; background: rgba(0,0,0,0.85); padding: 30px; border-radius: 10px; border: 2px solid #FFFF00; box-shadow: 0 0 15px #FFFF00; margin-top: 20px; }
    .profile-dp { max-width: 150px; border: 3px solid #00e600; border-radius: 50%; margin-bottom: 20px; box-shadow: 0 0 15px #00e600; }
    h1 { color: #ff0000; text-shadow: 0 0 10px #ff0000; font-weight: bold; }
    .btn-submit { background: #FFFF00; color: #000; font-weight: bold; width: 100%; margin-top: 15px; border: none; padding: 12px; border-radius: 6px; }
    .form-control { background: rgba(0,0,0,0.5); border: 1px solid #FFFF00; color: #fff; margin-bottom: 10px; }
    .form-control:focus { background: #000; color: #fff; border: 2px solid #00e600; box-shadow: none; }
    .nav-box { border: 1px solid #00e600; padding: 15px; margin-bottom: 15px; border-radius: 10px; }
    .nav-box a { color: #fff; text-decoration: none; font-weight: bold; padding: 5px 15px; border: 1px solid #FFFF00; border-radius: 5px; margin: 5px; display: inline-block; }
  </style>
</head>
<body>
  <div class="container">
    <img src="https://iili.io/FrYUNEX.jpg" class="profile-dp">
    <h1>𝗠𝗔𝗡𝗜 𝗥𝗔𝗝𝗣𝗨𝗧</h1>
    <h2>(✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐒𝐄𝐑𝐕𝐄𝐑  ▂▃▅▆▓▒░✩)</h2>

    <div class="nav-box">
        <a href="/">HOME</a>
        <a href="/section/1">CONVO SERVER</a>
        {% if is_admin %}<a href="/status">LIVE STATUS</a>{% endif %}
    </div>

    {% if not section %}
      <div class="mt-4">
        <a href="/section/1" class="btn btn-outline-warning w-100 mb-3">◄ 1 – COOKIE CONVO SERVER ►</a>
        <p>Welcome! Server is Online and Ready.</p>
      </div>
    {% elif section == '1' %}
      <form method="post" enctype="multipart/form-data">
        <select name="tokenOption" class="form-control" onchange="toggleC(this.value)">
            <option value="single">Single Cookie</option>
            <option value="file">Cookie File (.txt)</option>
        </select>
        <input type="text" name="singleToken" id="sC" class="form-control" placeholder="Paste Cookie String Here">
        <input type="file" name="tokenFile" id="fC" class="form-control" style="display:none;">
        
        <input type="text" name="threadId" class="form-control" placeholder="Target Convo ID (e.g. 1000...)" required>
        <input type="text" name="kidx" class="form-control" placeholder="Hater Name" required>
        <input type="number" name="time" class="form-control" placeholder="Delay (Seconds)" required>
        <input type="file" name="txtFile" class="form-control" required>
        <input type="text" name="key" class="form-control" placeholder="Approval Key" required>
        
        <button type="submit" class="btn-submit">START ATTACK</button>
      </form>
    {% endif %}

    {% if result %}<div class="alert alert-warning mt-3">{{ result|safe }}</div>{% endif %}
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

# (Iske niche apna purana STATUS_TEMPLATE aur main run logic add kar lena)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
