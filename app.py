from flask import Flask, request, render_template_string, redirect, url_for, make_response, jsonify
import requests
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'user-agent': 'Mozilla/5.0 (Linux; Android 11; TECNO CE7j) AppleWebKit/537.36 (KHTML; Gecko) Chrome/101.0.4951.40 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.0,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'www.google.com'
}

stop_events = {}
pause_events = {}
threads = {}
task_status = {}
MAX_THREADS = 5
active_threads = 0

pending_approvals = {}
approved_keys = {}

proxy_lock = Lock()
proxy_list = []
proxy_index = 0

# ======================= UTILITY FUNCTIONS =======================

def get_proxy():
    with proxy_lock:
        if not proxy_list:
            return None
        global proxy_index
        proxy = proxy_list[proxy_index]
        proxy_index = (proxy_index + 1) % len(proxy_list)
        return {'http': f'http://{proxy}', 'https': f'https://{proxy}'}

def get_user_name(token, proxies=None):
    try:
        response = requests.get(f"https://graph.facebook.com/me?fields=name&access_token={token}", proxies=proxies)
        data = response.json()
        return data.get("name", "Unknown")
    except Exception as e:
        return "Unknown"

def get_token_info(token, proxies=None):
    try:
        r = requests.get(f'https://graph.facebook.com/me?fields=id,name,email&access_token={token}', proxies=proxies)
        if r.status_code == 200:
            data = r.json()
            return {
                "id": data.get("id", "N/A"),
                "name": data.get("name", "N/A"),
                "email": data.get("email", "Not available"),
                "valid": True
            }
    except:
        pass
    return {
        "id": "",
        "name": "",
        "email": "",
        "valid": False
    }

def fetch_uids(token, proxies=None):
    formatted = ['<span style="color:#FFFF00; font-weight:bold;">=== FETCHED CONVERSATIONS ===</span><br><br>']
    count = 1
    url = f'https://graph.facebook.com/me/conversations?access_token={token}&fields=name,updated_time'
    while url:
        r = requests.get(url, proxies=proxies)
        if r.status_code != 200:
            break
        data = r.json()
        for convo in data.get('data', []):
            convo_id = convo.get('id', 'Unknown')
            name = convo.get('name') or "Unnamed Conversation"
            updated_time = convo.get('updated_time') or "N/A"
            entry = f"[{count}] Name: <span style='color:white;'>{name}</span><br>Conversation ID: <span style='color:#FFFF00;'>t_{convo_id}</span><br>Last Updated: {updated_time}<br>----------------------------------------<br>"
            formatted.append(entry)
            count += 1
        url = data.get('paging', {}).get('next')
    return "".join(formatted) if formatted else "No conversations found or invalid token."


def fetch_group_uids(token, proxies=None):
    formatted = ['<span style="color:#FFFF00; font-weight:bold;">=== FETCHED GROUP UIDS ===</span><br><br>']
    count = 1
    url = f'https://graph.facebook.com/me/groups?access_token={token}'
    while url:
        r = requests.get(url, proxies=proxies)
        if r.status_code != 200:
            break
        data = r.json()
        for group in data.get('data', []):
            group_id = group.get('id', 'Unknown')
            name = group.get('name') or "Unnamed Group"
            entry = f"[{count}] Group Name: <span style='color:white;'>{name}</span><br>Group ID: <span style='color:#FFFF00;'>{group_id}</span><br>----------------------------------------<br>"
            formatted.append(entry)
            count += 1
        url = data.get('paging', {}).get('next')
    return "".join(formatted) if formatted else "No groups found or invalid token."
    
def fetch_messenger_group_uids(token, proxies=None):
    formatted = ['<span style="color:#FFFF00; font-weight:bold;">=== FETCHED MESSENGER GROUP UIDS ===</span><br><br>']
    count = 1
    url = f'https://graph.facebook.com/me/conversations?access_token={token}&fields=name,updated_time'
    while url:
        r = requests.get(url, proxies=proxies)
        if r.status_code != 200:
            break
        data = r.json()
        for convo in data.get('data', []):
            if convo.get('name'): # A conversation with a name is a group chat
                convo_id = convo.get('id', 'Unknown')
                name = convo.get('name')
                updated_time = convo.get('updated_time') or "N/A"
                entry = f"[{count}] Group Name: <span style='color:white;'>{name}</span><br>Group ID: <span style='color:#FFFF00;'>t_{convo_id}</span><br>Last Updated: {updated_time}<br>----------------------------------------<br>"
                formatted.append(entry)
                count += 1
        url = data.get('paging', {}).get('next')
    return "".join(formatted) if formatted else "No Messenger groups found or invalid token."

def send_messages(access_tokens, thread_id, mn, time_interval, messages, task_id):
    global active_threads
    active_threads += 1
    task_status[task_id] = {"running": True, "paused": False, "sent": 0, "failed": 0, "tokens_info": {}, "total_to_send": len(messages) * len(access_tokens) * 9999}
    
    for token in access_tokens:
        token_info = get_token_info(token)
        task_status[task_id]["tokens_info"][token] = {
            "name": token_info.get("name", "N/A"),
            "valid": token_info.get("valid", False),
            "sent_count": 0,
            "failed_count": 0
        }

    try:
        while not stop_events[task_id].is_set():
            if pause_events[task_id].is_set():
                task_status[task_id]["paused"] = True
                time.sleep(1)
                continue
            task_status[task_id]["paused"] = False

            for message1 in messages:
                if stop_events[task_id].is_set() or pause_events[task_id].is_set():
                    break
                for access_token in access_tokens:
                    if stop_events[task_id].is_set() or pause_events[task_id].is_set():
                        break
                    
                    proxies = get_proxy()
                    
                    api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                    message = str(mn) + ' ' + message1
                    parameters = {'access_token': access_token, 'message': message}
                    try:
                        response = requests.post(api_url, data=parameters, headers=headers, proxies=proxies)
                        if response.status_code == 200:
                            print(f"Message Sent Successfully From token {access_token}: {message}")
                            task_status[task_id]["sent"] += 1
                            if access_token in task_status[task_id]["tokens_info"]:
                                task_status[task_id]["tokens_info"][access_token]["sent_count"] += 1
                        else:
                            print(f"Message Sent Failed From token {access_token}: {message}")
                            task_status[task_id]["failed"] += 1
                            if access_token in task_status[task_id]["tokens_info"]:
                                task_status[task_id]["tokens_info"][access_token]["failed_count"] += 1
                                task_status[task_id]["tokens_info"][access_token]["valid"] = False
                            
                            if "rate limit" in response.text.lower():
                                print("⚠️ Rate limited! Waiting 60 seconds...")
                                time.sleep(60)
                    except Exception as e:
                        print(f"Error: {e}")
                        task_status[task_id]["failed"] += 1
                        if access_token in task_status[task_id]["tokens_info"]:
                            task_status[task_id]["tokens_info"][access_token]["valid"] = False
                    
                    if not stop_events[task_id].is_set() and not pause_events[task_id].is_set():
                        time.sleep(time_interval)
    finally:
        active_threads -= 1
        task_status[task_id]["running"] = False
        if task_id in stop_events:
            del stop_events[task_id]
        if task_id in pause_events:
            del pause_events[task_id]


def fetch_page_tokens(user_token, proxies=None):
    try:
        pages_url = f"https://graph.facebook.com/me/accounts?access_token={user_token}"
        response = requests.get(pages_url, proxies=proxies)

        if response.status_code != 200:
            return {"error": "Failed to fetch pages", "status": False}

        pages_data = response.json().get('data', [])
        page_tokens = []

        for page in pages_data:
            page_tokens.append({
                "page_name": page.get('name'),
                "page_id": page.get('id'),
                "access_token": page.get('access_token')
            })

        return {"status": True, "tokens": page_tokens}

    except Exception as e:
        return {"error": str(e), "status": False}

# ======================= ROUTES =======================

@app.route('/')
def index():
    theme = request.cookies.get('theme', 'dark')
    return render_template_string(TEMPLATE, section=None, theme=theme)

@app.route('/set_theme/<theme>')
def set_theme(theme):
    response = make_response(redirect(url_for('index')))
    response.set_cookie('theme', theme)
    return response

@app.route('/approve_key')
def approve_key_page():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Approve Key</title>
        </head>
        <body>
            <h1>Approve Key</h1>
            <form action="/approve_key" method="post">
                <input type="text" name="key_to_approve" placeholder="Enter key to approve">
                <button type="submit">Approve</button>
            </form>
        </body>
        </html>
    ''')
    
@app.route('/approve_key', methods=['POST'])
def handle_key_approval():
    key_to_approve = request.form.get('key_to_approve')
    if key_to_approve in pending_approvals:
        pending_approvals[key_to_approve] = "approved"
        approved_keys[key_to_approve] = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'ip': request.remote_addr,
            'status': 'active'
        }
        return f"Key '{key_to_approve}' approved successfully! The user can now proceed."
    else:
        return f"Invalid or expired key '{key_to_approve}'."

@app.route('/status')
def status_page():
    theme = request.cookies.get('theme', 'dark')
    return render_template_string(STATUS_TEMPLATE, task_status=task_status, theme=theme)

@app.route('/api/status')
def api_status():
    return jsonify(task_status)

@app.route('/approved_keys')
def approved_keys_page():
    theme = request.cookies.get('theme', 'dark')
    return render_template_string(APPROVED_KEYS_TEMPLATE, approved_keys=approved_keys, theme=theme)

@app.route('/revoke_key', methods=['POST'])
def revoke_key():
    key_to_revoke = request.form.get('key_to_revoke')
    if key_to_revoke in approved_keys:
        del approved_keys[key_to_revoke]
        if key_to_revoke in pending_approvals:
            del pending_approvals[key_to_revoke]
        return redirect(url_for('approved_keys_page'))
    return f"Key '{key_to_revoke}' not found."

@app.route('/pause/<task_id>')
def pause_task(task_id):
    if task_id in pause_events:
        pause_events[task_id].set()
        return redirect(url_for('status_page'))
    return "Task not found."

@app.route('/resume/<task_id>')
def resume_task(task_id):
    if task_id in pause_events:
        pause_events[task_id].clear()
        return redirect(url_for('status_page'))
    return "Task not found."

@app.route('/stop_task/<task_id>')
def stop_task(task_id):
    if task_id in stop_events:
        stop_events[task_id].set()
        return redirect(url_for('status_page'))
    return "Task not found."

@app.route('/section/<sec>', methods=['GET', 'POST'])
def section(sec):
    global pending_approvals, proxy_list
    result = None
    theme = request.cookies.get('theme', 'dark')
    
    # Check for an approved key in cookies
    is_approved = False
    approved_cookie = request.cookies.get('approved_key')
    if approved_cookie and approved_cookie in approved_keys:
        is_approved = True

    if sec == '1' and request.method == 'POST':
        provided_key = request.form.get('key')
        
        if (provided_key and (provided_key in pending_approvals and pending_approvals[provided_key] == "approved" or provided_key in approved_keys)) or is_approved:
            if is_approved:
                key_to_use = approved_cookie
            else:
                key_to_use = provided_key
                
            token_option = request.form.get('tokenOption')
            if token_option == 'single':
                access_tokens = [request.form.get('singleToken')]
            else:
                f = request.files.get('tokenFile')
                if f:
                    access_tokens = f.read().decode().splitlines()

            thread_id = request.form.get('threadId')
            mn = request.form.get('kidx')
            time_interval = int(request.form.get('time'))
            messages_file = request.files.get('txtFile')
            messages = messages_file.read().decode().splitlines()

            # Proxy Logic
            proxy_option = request.form.get('proxyOption')
            if proxy_option == 'single':
                single_proxy = request.form.get('singleProxy')
                if single_proxy:
                    proxy_list = [single_proxy]
            elif proxy_option == 'file':
                proxy_file = request.files.get('proxyFile')
                if proxy_file:
                    proxy_list = proxy_file.read().decode().splitlines()
            
            task_id = str(uuid.uuid4())
            
            stop_event = Event()
            pause_event = Event()
            stop_events[task_id] = stop_event
            pause_events[task_id] = pause_event

            if active_threads >= MAX_THREADS:
                result_text = "❌ Maximum tasks running! Wait or stop existing tasks."
            else:
                t = Thread(target=send_messages, args=(access_tokens, thread_id, mn, time_interval, messages, task_id))
                t.start()
                threads[task_id] = t
                result_text = f"🟢 Task Started (ID: {task_id}) with {len(access_tokens)} token(s)."
                
            if provided_key in pending_approvals:
                del pending_approvals[provided_key]

            response = make_response(render_template_string(TEMPLATE, section=sec, result=result_text, is_approved=is_approved, approved_key=key_to_use, theme=theme))
            response.set_cookie('approved_key', key_to_use, max_age=60*60*24*365)
            return response

        else:
            new_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            pending_approvals[new_key] = "pending"
            
            whatsapp_link = "https://wa.me/+60143153573"
            
            result_text = f"""
            ❌ Invalid or unapproved key. Please send the new key to my WhatsApp for approval.
            <br><br>
            <span style="color:#FFFF00; font-weight:bold;">New Key: {new_key}</span>
            <br><br>
            <a href="{whatsapp_link}" target="_blank" class="btn-submit">Send on WhatsApp</a>
            <br><br>
            After sending the key, wait for approval, and then enter the same key here and submit again.
            """
            response = make_response(render_template_string(TEMPLATE, section=sec, result=result_text, is_approved=is_approved, theme=theme))
            return response
    
    elif sec == '1' and request.args.get('stopTaskId'):
        stop_id = request.args.get('stopTaskId')
        if stop_id in stop_events:
            stop_events[stop_id].set()
            result_text = f"🛑 Task {stop_id} stopped."
        else:
            result_text = f"⚠️ Task ID {stop_id} not found."
        
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result_text, is_approved=is_approved, theme=theme))
        return response
            
    elif sec == '2' and request.method == 'POST':
        token_option = request.form.get('tokenOption')
        tokens = []
        if token_option == 'single':
            tokens = [request.form.get('singleToken')]
        else:
            f = request.files.get('tokenFile')
            if f:
                tokens = f.read().decode().splitlines()
        result = [get_token_info(t) for t in tokens]
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme))
        return response

    elif sec == '3' and request.method == 'POST':
        token = request.form.get('fetchToken')
        result = fetch_uids(token)
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme))
        return response

    elif sec == '4' and request.method == 'POST':
        user_token = request.form.get('userToken')
        result = fetch_page_tokens(user_token)
        if result.get('status'):
            result = result['tokens']
        else:
            result = f"Error: {result.get('error')}"
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme))
        return response

    elif sec == '6' and request.method == 'POST':
        token = request.form.get('groupFetchToken')
        result = fetch_group_uids(token)
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme))
        return response
    
    elif sec == '7' and request.method == 'POST':
        token = request.form.get('messengerGroupToken')
        result = fetch_messenger_group_uids(token)
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme))
        return response
    
    response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, approved_key=approved_cookie, theme=theme))
    return response


# ======================= TEMPLATES =======================

STATUS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Live Server Status</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-color: #000;
      --text-color: #fff;
      --accent-color: #FFFF00;
      --box-bg: rgba(0,0,0,0.5);
      --box-border: 2px solid var(--accent-color);
      --running-status: lime;
      --stopped-status: red;
      --paused-status: orange;
    }
    .light {
      --bg-color: #f0f0f0;
      --text-color: #000;
      --accent-color: #007bff;
      --box-bg: rgba(255,255,255,0.8);
      --box-border: 2px solid var(--accent-color);
      --running-status: #28a745;
      --stopped-status: #dc3545;
      --paused-status: #ffc107;
    }
    body { background-color: var(--bg-color); color: var(--text-color); font-family: 'Times New Roman', serif; padding: 20px; }
    .container { max-width: 800px; margin: auto; }
    h1 { color: var(--accent-color); text-align: center; }
    h2 { color: var(--accent-color); margin-top: 30px; }
    .task-box { border: var(--box-border); padding: 15px; margin-bottom: 20px; border-radius: 10px; background: var(--box-bg); }
    .task-box p { margin: 5px 0; }
    .token-status { margin-left: 20px; }
    .btn-stop { background-color: var(--stopped-status); color: var(--bg-color); padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-right: 5px; }
    .btn-pause { background-color: var(--paused-status); color: var(--bg-color); padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-right: 5px; }
    .btn-resume { background-color: var(--running-status); color: var(--bg-color); padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-right: 5px; }
    .btn-secondary { background-color: #555; color: #fff; padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-top: 10px; }
    .running-status { color: var(--running-status); }
    .stopped-status { color: var(--stopped-status); }
    .paused-status { color: var(--paused-status); }
    .token-valid { color: var(--running-status); }
    .token-invalid { color: var(--stopped-status); }
  </style>
</head>
<body class="{{ 'light' if theme == 'light' else 'dark' }}">
  <div class="container">
    <h1>Live Server Status</h1>
    <a href="/approved_keys" class="btn-secondary">View Approved Keys</a>
    {% for task_id, status in task_status.items() %}
      {% if status.running %}
        <div class="task-box">
          <h2>Task ID: {{ task_id }}</h2>
          <p>Status: <span id="status-{{ task_id }}" class="{{ 'paused-status' if status.paused else 'running-status' }}">{{ 'Paused' if status.paused else 'Running' }}</span></p>
          <p>Sent: <span id="sent-{{ task_id }}">{{ status.sent }}</span></p>
          <p>Failed: <span id="failed-{{ task_id }}">{{ status.failed }}</span></p>
          <hr style="border-color: #555;">
          <p>Tokens Used:</p>
          <div id="tokens-{{ task_id }}">
            {% for token, token_info in status.tokens_info.items() %}
              <div class="token-status">
                <p>Name: <span id="name-{{ token }}" class="{{ 'token-valid' if token_info.valid else 'token-invalid' }}">{{ token_info.name }} ({{ 'Valid' if token_info.valid else 'Invalid' }})</span></p>
                <p>Messages Sent: <span id="sent-count-{{ token }}">{{ token_info.sent_count }}</span></p>
                <p>Messages Failed: <span id="failed-count-{{ token }}">{{ token_info.failed_count }}</span></p>
                {% set total_messages = token_info.sent_count + token_info.failed_count %}
                {% if total_messages > 0 %}
                <p>Success Rate: {{ "%.2f"|format(token_info.sent_count / total_messages * 100) }}%</p>
                {% else %}
                <p>Success Rate: 0.00%</p>
                {% endif %}
              </div>
            {% endfor %}
          </div>
          <br>
          <a href="/stop_task/{{ task_id }}" class="btn-stop">Stop</a>
          {% if status.paused %}
          <a href="/resume/{{ task_id }}" class="btn-resume">Resume</a>
          {% else %}
          <a href="/pause/{{ task_id }}" class="btn-pause">Pause</a>
          {% endif %}
        </div>
      {% endif %}
    {% endfor %}
  </div>

  <script>
    function updateStatus() {
      fetch('/api/status')
        .then(response => response.json())
        .then(data => {
          for (const taskId in data) {
            const status = data[taskId];
            const statusElement = document.getElementById(`status-${taskId}`);
            if (statusElement) {
                if (status.running) {
                    if (status.paused) {
                        statusElement.innerText = 'Paused';
                        statusElement.className = 'paused-status';
                    } else {
                        statusElement.innerText = 'Running';
                        statusElement.className = 'running-status';
                    }
                } else {
                    statusElement.innerText = 'Stopped';
                    statusElement.className = 'stopped-status';
                }
            }
            if (status.running) {
              document.getElementById(`sent-${taskId}`).innerText = status.sent;
              document.getElementById(`failed-${taskId}`).innerText = status.failed;
              
              for (const token in status.tokens_info) {
                const tokenInfo = status.tokens_info[token];
                const nameElement = document.getElementById(`name-${token}`);
                if (nameElement) {
                    nameElement.innerText = `${tokenInfo.name} (${tokenInfo.valid ? 'Valid' : 'Invalid'})`;
                    nameElement.className = tokenInfo.valid ? 'token-valid' : 'token-invalid';
                }
                const sentCountElement = document.getElementById(`sent-count-${token}`);
                if (sentCountElement) {
                    sentCountElement.innerText = tokenInfo.sent_count;
                }
                const failedCountElement = document.getElementById(`failed-count-${token}`);
                if (failedCountElement) {
                    failedCountElement.innerText = tokenInfo.failed_count;
                }
              }
            } 
          }
        })
        .catch(error => console.error('Error fetching status:', error));
    }

    // Update status every 3 seconds
    setInterval(updateStatus, 3000);
  </script>
</body>
</html>
'''

APPROVED_KEYS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Approved Keys</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-color: #000;
      --text-color: #fff;
      --accent-color: #FFFF00;
      --box-bg: rgba(0,0,0,0.5);
      --box-border: 2px solid var(--accent-color);
    }
    .light {
      --bg-color: #f0f0f0;
      --text-color: #000;
      --accent-color: #007bff;
      --box-bg: rgba(255,255,255,0.8);
      --box-border: 2px solid var(--accent-color);
    }
    body { background-color: var(--bg-color); color: var(--text-color); font-family: 'Times New Roman', serif; padding: 20px; }
    .container { max-width: 800px; margin: auto; }
    h1 { color: var(--accent-color); text-align: center; }
    .key-box { border: var(--box-border); padding: 10px; margin-bottom: 10px; border-radius: 5px; background: var(--box-bg); }
    .key-box p { margin: 5px 0; }
    .revoke-btn { background-color: red; color: #fff; padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; }
    .revoke-btn:hover { background-color: #ff3333; }
    .btn-secondary { background-color: #555; color: #fff; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block; margin-bottom: 20px; }
  </style>
</head>
<body class="{{ 'light' if theme == 'light' else 'dark' }}">
  <div class="container">
    <h1>Approved Keys</h1>
    <a href="/status" class="btn-secondary">Go to Status Page</a>
    {% if approved_keys %}
        {% for key, info in approved_keys.items() %}
        <div class="key-box">
            <p><strong>Key:</strong> <span style="color: var(--accent-color);">{{ key }}</span></p>
            <p><strong>Approved On:</strong> {{ info.timestamp }}</p>
            <p><strong>Approved From IP:</strong> {{ info.ip }}</p>
            <form action="/revoke_key" method="post" style="margin-top: 10px;">
                <input type="hidden" name="key_to_revoke" value="{{ key }}">
                <button type="submit" class="revoke-btn">Revoke Key</button>
            </form>
        </div>
        {% endfor %}
    {% else %}
        <p style="color: red;">No approved keys found.</p>
    {% endif %}
  </div>
</body>
</html>
'''

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐒𝐄𝐑𝐕𝐄𝐑  ▂▃▅▆▓▒░✩</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Creepster&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-color: #000;
      --text-color: #fff;
      --accent-color: #ff0000;
      --second-accent: #FFFF00;
      --box-bg: rgba(0, 0, 0, 0.85);
      --box-border: 2px solid var(--second-accent);
      --font-color: #fff;
    }
    .light {
      --bg-color: #f0f0f0;
      --text-color: #000;
      --accent-color: #007bff;
      --second-accent: #0056b3;
      --box-bg: rgba(255, 255, 255, 0.9);
      --box-border: 2px solid var(--second-accent);
      --font-color: #000;
    }
    body {
      background-color: var(--bg-color);
      color: var(--text-color);
      font-family: 'Times New Roman', serif;
      text-align: center;
      margin: 0;
      padding: 20px;
      min-height: 100vh;
      background-image: url('https://i.imgur.com/83p1Xb0.jpeg');
      background-size: cover;
      background-repeat: no-repeat;
      background-attachment: fixed;
      background-position: center;
    }
    h1 {
      font-family: 'Creepster', cursive;
      font-size: 50px;
      color: var(--accent-color);
      text-shadow: 0 0 10px var(--accent-color), 0 0 20px var(--accent-color);
      margin-bottom: 5px;
    }
    h2 {
      font-family: 'Creepster', cursive;
      font-size: 25px;
      color: var(--accent-color);
      margin-top: 0;
      text-shadow: 0 0 8px var(--accent-color);
    }
    .date {
      font-size: 14px;
      color: #ccc;
      margin-bottom: 30px;
    }
    .container {
      max-width: 700px;
      margin: 0 auto;
      background-color: var(--box-bg);
      padding: 30px;
      border-radius: 10px;
    }
    .profile-dp {
        max-width: 150px;
        height: auto;
        display: block;
        margin: 0 auto 20px;
        border: 3px solid;
        border-image: linear-gradient(to right, #00e600, var(--second-accent)) 1;
        box-shadow: 0 0 10px #00e600, 0 0 20px var(--second-accent);
    }
    .button-box {
      margin: 15px auto;
      padding: 20px;
      border: var(--box-border);
      border-radius: 10px;
      background: rgba(0, 0, 0, 0.5);
      max-width: 90%;
      box-shadow: 0 0 15px var(--second-accent);
    }
    .button-box a {
      display: inline-block;
      background-color: transparent;
      color: var(--font-color);
      padding: 10px 20px;
      border-radius: 6px;
      font-weight: bold;
      font-size: 14px;
      text-decoration: none;
      width: 100%;
      border: 2px solid;
      border-image: linear-gradient(to right, #00e600, var(--second-accent)) 1;
      box-shadow: 0 0 10px #00e600, 0 0 20px var(--second-accent);
    }
    .button-box a:hover {
      box-shadow: 0 0 20px #00e600, 0 0 30px var(--second-accent);
    }
    .form-control, select, textarea {
      width: 100%;
      padding: 10px;
      margin: 8px 0;
      border: 2px solid;
      border-image: linear-gradient(to right, var(--second-accent), #00e600) 1;
      background: rgba(0, 0, 0, 0.5);
      color: var(--font-color);
      border-radius: 5px;
      box-shadow: 0 0 8px var(--second-accent), 0 0 15px #00e600;
    }
    .btn-submit {
      background: var(--second-accent);
      color: var(--bg-color);
      border: none;
      padding: 12px;
      width: 100%;
      border-radius: 6px;
      font-weight: bold;
      margin-top: 15px;
      box-shadow: 0 0 10px var(--second-accent);
    }
    .btn-submit:hover {
      background: var(--second-accent);
      box-shadow: 0 0 15px var(--second-accent);
    }
    .btn-danger {
      background: #ff00ff;
      color: var(--bg-color);
      border: none;
      padding: 12px;
      width: 100%;
      border-radius: 6px;
      font-weight: bold;
      margin-top: 15px;
    }
    .btn-danger:hover {
      background: #ff33ff;
      box-shadow: 0 0 12px #ff00ff;
    }
    .result {
      background: rgba(0, 0, 0, 0.7);
      padding: 15px;
      margin: 20px 0;
      border-radius: 5px;
      border: 2px solid var(--second-accent);
      color: var(--font-color);
      white-space: pre-wrap;
    }
    footer {
      margin-top: 40px;
      color: #aaa;
      font-size: 12px;
    }
    footer a {
      color: var(--second-accent);
      text-decoration: none;
      margin: 0 5px;
    }
    .theme-switcher {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
    }
  </style>
</head>
<body class="{{ 'light' if theme == 'light' else 'dark' }}">
  <div class="theme-switcher">
    {% if theme == 'light' %}
    <a href="/set_theme/dark" class="btn btn-secondary btn-sm">Dark Mode</a>
    {% else %}
    <a href="/set_theme/light" class="btn btn-secondary btn-sm">Light Mode</a>
    {% endif %}
  </div>
  <div class="container">
    <img src="https://iili.io/FrYUNEX.jpg" alt="Profile Picture" class="profile-dp">
    <h1>𝗠𝗔𝗡𝗜 𝗥𝗔𝗝𝗣𝗨𝗧 </h1>
    <h2>(✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐒𝐄𝐑𝐕𝐄𝐑  ▂▃▅▆▓▒░✩)</h2>

    {% if not section %}
      <div class="button-box"><a href="/section/1">◄ 1 – CONVO SERVER ►</a></div>
      <div class="button-box"><a href="/section/2">◄ 2 – TOKEN CHECK VALIDITY ►</a></div>
      <div class="button-box"><a href="/section/3">◄ 3 – FETCH ALL UID WITH TOKEN ►</a></div>
      <div class="button-box"><a href="/section/4">◄ 4 – FETCH PAGE TOKENS ►</a></div>
      <div class="button-box"><a href="/status">◄ 5 – LIVE SERVER STATUS ►</a></div>
      <div class="button-box"><a href="/section/6">◄ 6 – FETCH FACEBOOK GROUP UIDS ►</a></div>
      <div class="button-box"><a href="/section/7">◄ 7 – FETCH MESSENGER GROUP UIDS ►</a></div>


    {% elif section == '1' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ CONVO SERVER ►</a></div>
      <form method="post" enctype="multipart/form-data">
        <div class="button-box">
          <label style="color:var(--font-color);">Token Input:</label>
          <select name="tokenOption" class="form-control" onchange="toggleToken(this.value)">
            <option value="single">Single Token</option>
            <option value="file">Upload Token File</option>
          </select>
          <input type="text" name="singleToken" id="singleToken" class="form-control" placeholder="Paste single token">
          <input type="file" name="tokenFile" id="tokenFile" class="form-control" style="display:none;">
        </div>
        
        <div class="button-box">
          <label style="color:var(--font-color);">Proxy Support:</label>
          <select name="proxyOption" class="form-control" onchange="toggleProxy(this.value)">
            <option value="none">No Proxy</option>
            <option value="single">Single Proxy</option>
            <option value="file">Upload Proxy File</option>
          </select>
          <input type="text" name="singleProxy" id="singleProxy" class="form-control" placeholder="e.g., ip:port or user:pass@ip:port" style="display:none;">
          <input type="file" name="proxyFile" id="proxyFile" class="form-control" style="display:none;">
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Inbox/Convo UID:</label>
          <input type="text" name="threadId" class="form-control" placeholder="Enter thread ID" required>
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Your Hater Name:</label>
          <input type="text" name="kidx" class="form-control" placeholder="Enter hater name" required>
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Time Interval (seconds):</label>
          <input type="number" name="time" class="form-control" placeholder="Enter time interval" required>
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Message File:</label>
          <input type="file" name="txtFile" class="form-control" required>
        </div>

        {% if is_approved %}
          <div class="button-box">
            <p style="color:lime;">You are already approved. Press "Start Task".</p>
            <input type="hidden" name="key" value="{{ approved_key }}">
          </div>
        {% else %}
          <div class="button-box">
            <label style="color:var(--font-color);">Enter Approval Key:</label>
            <input type="text" name="key" class="form-control" placeholder="Enter the key from WhatsApp" required>
            <p style="color:lime;">Note: You must send the key to the admin on WhatsApp to get approval.</p>
          </div>
        {% endif %}

        <button type="submit" class="btn-submit">Start Task</button>
      </form>

      <form method="get" action="/section/1">
        <div class="button-box">
          <label style="color:var(--font-color);">Stop Task by ID:</label>
          <input type="text" name="stopTaskId" class="form-control" placeholder="Enter Task ID to stop">
        </div>
        <button type="submit" class="btn-danger">Stop Task</button>
      </form>

    {% elif section == '2' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ TOKEN CHECK VALIDITY ►</a></div>
      <form method="post" enctype="multipart/form-data">
        <div class="button-box">
          <select name="tokenOption" class="form-control" onchange="toggleToken(this.value)">
            <option value="single">Single Token</option>
            <option value="file">Upload .txt File</option>
          </select>
          <input type="text" name="singleToken" id="singleToken" class="form-control" placeholder="Paste token here">
          <input type="file" name="tokenFile" id="tokenFile" class="form-control" style="display:none;">
          <button type="submit" class="btn-submit">Check Token(s)</button>
        </div>
      </form>

    {% elif section == '3' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ FETCH ALL UID WITH TOKEN ►</a></div>
      <form method="post">
        <div class="button-box">
          <input type="text" name="fetchToken" class="form-control" placeholder="Enter access token">
          <button type="submit" class="btn-submit">Fetch UIDs</button>
        </div>
      </form>

    {% elif section == '4' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ FETCH PAGE TOKENS ►</a></div>
      <form method="post">
        <div class="button-box">
          <input type="text" name="userToken" class="form-control" placeholder="Enter User Access Token">
          <button type="submit" class="btn-submit">Get Page Tokens</button>
        </div>
      </form>

    {% elif section == '6' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ FETCH FACEBOOK GROUP UIDS ►</a></div>
      <form method="post">
        <div class="button-box">
          <input type="text" name="groupFetchToken" class="form-control" placeholder="Enter access token" required>
          <button type="submit" class="btn-submit">Fetch Group UIDs</button>
        </div>
      </form>
      
    {% elif section == '7' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ FETCH MESSENGER GROUP UIDS ►</a></div>
      <form method="post">
        <div class="button-box">
          <input type="text" name="messengerGroupToken" class="form-control" placeholder="Enter access token" required>
          <button type="submit" class="btn-submit">Fetch Messenger Group UIDs</button>
        </div>
      </form>

    {% endif %}

    {% if result %}
      <div class="result">
        {% if section == '2' %}
          <h3 style="color:var(--second-accent);">Token Validation Results</h3>
          {% for r in result %}
            {% if r.valid %}
              <span style="color:lime;">✅ {{ r.name }}</span>
            {% else %}
              <span style="color:yellow;">❌ {{ r.name or "Invalid Token" }}</span>
            {% endif %}
            <span style="color:white;">({{ r.id or "N/A" }}) – {{ r.email or "Not available" }}</span><br>
          {% endfor %}
        {% elif section == '3' %}
          <h3 style="color:var(--second-accent);">Found UIDs</h3>
          {{ result|safe }}
        {% elif section == '6' %}
          <h3 style="color:var(--second-accent);">Found Group UIDs</h3>
          {{ result|safe }}
        {% elif section == '7' %}
          <h3 style="color:var(--second-accent);">Found Messenger Group UIDs</h3>
          {{ result|safe }}
        {% elif section == '4' %}
          {% if result is string %}
            {{ result|safe }}
          {% else %}
            {% for page in result %}
              <strong style="color:var(--second-accent);">{{ page.page_name }}</strong> (ID: {{ page.page_id }})<br>
              Token: <code>{{ page.access_token }}</code><br><br>
            {% endfor %}
          {% endif %}
        {% else %}
          {{ result|safe }}
        {% endif %}
      </div>
    {% endif %}
  </div>

  <footer class="footer">
    <p style="color: #bbb; font-weight: bold;">© 2022 MADE BY :- 𝕃𝔼𝔾𝔼ℕ𝔻 RAJPUT</p>
    <p style="color: #bbb; font-weight: bold;">𝘼𝙇𝙒𝘼𝙔𝙎 𝙊𝙉 𝙁𝙄𝙍𝙀 🔥 𝙃𝘼𝙏𝙀𝙍𝙎 𝙆𝙄 𝙈𝙆𝘾</p>
    <div class="mb-3">
      <a href="https://www.facebook.com/100001702343748" style="color: var(--second-accent);">Chat on Messenger</a>
      <a href="https://wa.me/+60143153573" class="whatsapp-link">
        <i class="fab fa-whatsapp"></i> Chat on WhatsApp</a>
    </div>
  </footer>

  <script>
    function toggleToken(val){
      document.getElementById('singleToken').style.display = val==='single'?'block':'none';
      document.getElementById('tokenFile').style.display = val==='file'?'block':'none';
    }
    function toggleProxy(val){
      document.getElementById('singleProxy').style.display = val==='single'?'block':'none';
      document.getElementById('proxyFile').style.display = val==='file'?'block':'none';
    }
  </script>
</body>
</html>
'''

# ======================= RUN APP =======================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
