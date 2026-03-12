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

# ======================= GLOBAL SETTINGS =======================

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
task_status = {}
task_owners = {}
pending_approvals = {}
approved_keys = {}
active_threads = 0
MAX_THREADS = 50

# Admin Password
ADMIN_SECRET_KEY = 'daku302' 

# ======================= COOKIE ENGINE =======================

def get_fb_tokens(session, thread_id):
    try:
        clean_id = thread_id.replace('t_', '')
        url = f'https://mbasic.facebook.com/messages/read/?tid={clean_id}'
        res = session.get(url, headers=headers)
        fb_dtsg = re.search(r'name="fb_dtsg" value="(.*?)"', res.text).group(1)
        jazoest = re.search(r'name="jazoest" value="(.*?)"', res.text).group(1)
        tids = re.search(r'name="tids" value="(.*?)"', res.text).group(1)
        www_base_domain = re.search(r'name="www_base_domain" value="(.*?)"', res.text).group(1)
        return {'fb_dtsg': fb_dtsg, 'jazoest': jazoest, 'tids': tids, 'www_base_domain': www_base_domain}
    except:
        return None

def send_messages(cookies, thread_id, mn, time_interval, messages, task_id):
    global active_threads
    active_threads += 1
    task_status[task_id] = {"running": True, "sent": 0, "failed": 0, "tokens_info": {}}
    
    try:
        msg_idx = 0
        while not stop_events[task_id].is_set():
            for cookie in cookies:
                if stop_events[task_id].is_set(): break
                try:
                    session = requests.Session()
                    c_dict = {c.strip().split('=')[0]: c.strip().split('=')[1] for c in cookie.split(';') if '=' in c}
                    session.cookies.update(c_dict)
                    fb_data = get_fb_tokens(session, thread_id)
                    
                    if fb_data:
                        full_msg = f"{mn} {messages[msg_idx % len(messages)]}"
                        payload = {'fb_dtsg': fb_data['fb_dtsg'], 'jazoest': fb_data['jazoest'], 'body': full_msg, 'send': 'Send', 'tids': fb_data['tids'], 'www_base_domain': fb_data['www_base_domain']}
                        res = session.post('https://mbasic.facebook.com/messages/send/', data=payload, headers=headers)
                        if res.status_code == 200: task_status[task_id]["sent"] += 1
                        else: task_status[task_id]["failed"] += 1
                    else: task_status[task_id]["failed"] += 1
                except: task_status[task_id]["failed"] += 1
                msg_idx += 1
                time.sleep(time_interval)
    finally:
        active_threads -= 1
        task_status[task_id]["running"] = False

# ======================= ROUTES & PAGES =======================

@app.route('/')
def index():
    is_admin = request.cookies.get('is_admin') == 'true'
    return render_template_string(MAIN_UI, section=None, is_admin=is_admin)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_SECRET_KEY:
            resp = make_response(redirect(url_for('admin_approve_dashboard')))
            resp.set_cookie('is_admin', 'true')
            return resp
    return '<h2>Admin Login</h2><form method="POST"><input type="password" name="password"><button>Login</button></form>'

@app.route('/admin/approve', methods=['GET', 'POST'])
def admin_approve_dashboard():
    if request.cookies.get('is_admin') != 'true': return redirect(url_for('admin_login'))
    if request.method == 'POST':
        key = request.form.get('key_to_approve')
        approved_keys[key] = {'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        pending_approvals.pop(key, None)
    return render_template_string(ADMIN_UI, pending=pending_approvals, approved=approved_keys)

@app.route('/section/1', methods=['GET', 'POST'])
def section1():
    result = None
    is_admin = request.cookies.get('is_admin') == 'true'
    if request.method == 'POST':
        key = request.form.get('key')
        if key in approved_keys or key == "MANI-BOSS":
            cookies = [request.form.get('singleToken')] if request.form.get('tokenOption')=='single' else request.files.get('tokenFile').read().decode().splitlines()
            thread_id = request.form.get('threadId')
            mn = request.form.get('kidx')
            interval = int(request.form.get('time'))
            msgs = request.files.get('txtFile').read().decode().splitlines()
            task_id = str(uuid.uuid4())
            stop_events[task_id] = Event()
            Thread(target=send_messages, args=(cookies, thread_id, mn, interval, msgs, task_id)).start()
            result = f"🟢 Started! Task ID: {task_id}"
        else:
            new_k = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            pending_approvals[new_k] = "pending"
            result = f"❌ Unapproved! Send Key: {new_k}"
    return render_template_string(MAIN_UI, section='1', result=result, is_admin=is_admin)

@app.route('/status')
def status():
    return render_template_string(STATUS_UI, task_status=task_status)

# ======================= UI TEMPLATES =======================

MAIN_UI = '''
<!DOCTYPE html><html><head><title>DAKU 302</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{background:#000;color:#fff;text-align:center;background-image:url('https://i.imgur.com/83p1Xb0.jpeg');background-size:cover;}
.container{max-width:600px;background:rgba(0,0,0,0.8);padding:20px;border:2px solid #FFFF00;margin-top:20px;border-radius:15px;}
.form-control{background:#111;color:#fff;border:1px solid #FFFF00;margin-bottom:10px;}
.btn-submit{background:#FFFF00;color:#000;width:100%;font-weight:bold;padding:10px;}</style></head>
<body><div class="container"><h1>𝗠𝗔𝗡𝗜 𝗥𝗔𝗝𝗣𝗨𝗧</h1><div class="mb-3"><a href="/" class="btn btn-sm btn-outline-info">Home</a> 
<a href="/section/1" class="btn btn-sm btn-outline-warning">Convo</a> <a href="/status" class="btn btn-sm btn-outline-success">Status</a>
{% if is_admin %}<a href="/admin/approve" class="btn btn-sm btn-outline-danger">Admin</a>{% endif %}</div>
{% if section == '1' %}<form method="post" enctype="multipart/form-data">
<select name="tokenOption" class="form-control"><option value="single">Single Cookie</option><option value="file">File</option></select>
<input type="text" name="singleToken" class="form-control" placeholder="Cookie String">
<input type="file" name="tokenFile" class="form-control">
<input type="text" name="threadId" class="form-control" placeholder="Convo ID" required>
<input type="text" name="kidx" class="form-control" placeholder="Hater Name" required>
<input type="number" name="time" class="form-control" placeholder="Delay" required>
<input type="file" name="txtFile" class="form-control" required>
<input type="text" name="key" class="form-control" placeholder="Approval Key" required>
<button type="submit" class="btn-submit">LAUNCH</button></form>
{% else %}<h3>Welcome to Cookie Server</h3><p>Select Section 1 to start attack.</p>{% endif %}
{% if result %}<div class="alert alert-info mt-3">{{ result|safe }}</div>{% endif %}</div></body></html>'''

ADMIN_UI = '''<!DOCTYPE html><html><body style="background:#000;color:#39ff14;font-family:monospace;padding:20px;">
<h1>ADMIN MANAGER</h1><h3>Pending Keys:</h3>
{% for k in pending %}<li>{{k}} <form method="POST"><input type="hidden" name="key_to_approve" value="{{k}}"><button type="submit">Approve</button></form></li>{% endfor %}
<hr><h3>Approved:</h3>{% for k,v in approved.items() %}<li>{{k}} - {{v.timestamp}}</li>{% endfor %}
<br><a href="/" style="color:cyan;">Back Home</a></body></html>'''

STATUS_UI = '''<!DOCTYPE html><html><body style="background:#000;color:lime;padding:20px;"><h1>TASK STATUS</h1>
{% for id, s in task_status.items() %}<div>ID: {{id}} | Sent: {{s.sent}} | Fail: {{s.failed}} | Running: {{s.running}}</div><hr>{% endfor %}
<a href="/" style="color:white;">Back</a></body></html>'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
