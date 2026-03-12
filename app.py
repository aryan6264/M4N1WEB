from flask import Flask, request, redirect, url_for, jsonify, session, g
import requests
import time
import threading
import uuid
import json 
import functools 
import re 
from bs4 import BeautifulSoup

app = Flask(__name__)

# ==========================================================
# CONFIG & DATA PATHS
# ==========================================================
app.secret_key = 'your_super_secret_key_change_this' 
ADMIN_USERNAME = 'MANI.302' 
ADMIN_PASSWORD = 'M4N1X2662' 
USERS_FILE = 'users.json' 

TASK_MANAGER = {} 
LOG_CAPTURE = []

# ==========================================================
# UTILITIES & SCRAPING LOGIC
# ==========================================================

def get_fb_tokens(session, url):
    """Page se fb_dtsg aur jazoest nikalne ke liye logic"""
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        fb_dtsg = soup.find('input', {'name': 'fb_dtsg'})['value']
        jazoest = soup.find('input', {'name': 'jazoest'})['value']
        return fb_dtsg, jazoest
    except:
        return None, None

def capture_output(text):
    global LOG_CAPTURE
    if len(LOG_CAPTURE) > 50: LOG_CAPTURE.pop(0)
    LOG_CAPTURE.append(f"{time.strftime('%I:%M:%S %p')} - {text}")

def capture_task_log(task_id, text):
    if task_id in TASK_MANAGER:
        task_info = TASK_MANAGER[task_id]
        if len(task_info['logs']) > 100: task_info['logs'].pop(0)
        task_info['logs'].append(f"{time.strftime('%I:%M:%S %p')} - {text}")

# ==========================================================
# USER MANAGEMENT (LOAD/SAVE)
# ==========================================================
def load_users():
    try:
        with open(USERS_FILE, 'r') as f: return json.load(f)
    except:
        initial = {ADMIN_USERNAME: {"password": ADMIN_PASSWORD, "is_approved": True, "is_admin": True, "tasks": []}}
        save_users(initial)
        return initial

def save_users(users_data):
    with open(USERS_FILE, 'w') as f: json.dump(users_data, f, indent=4)

# ==========================================================
# COOKIE WORKER FUNCTIONS (NEW LOGIC)
# ==========================================================

def run_sending_process(task_id, thread_id, haters_name, speed, cookies, messages, owner_username):
    """Cookie based Message Sending (Inbox/Group)"""
    num_messages = len(messages)
    max_cookies = len(cookies)
    message_counter = 0 
    
    capture_task_log(task_id, f"[i] Started Cookie-Task for Thread: {thread_id}")

    while TASK_MANAGER.get(task_id, {}).get('running', False):
        try:
            if TASK_MANAGER.get(task_id, {}).get('paused', False):
                time.sleep(1); continue
            
            cookie = cookies[message_counter % max_cookies].strip()
            message = messages[message_counter % num_messages].strip()
            full_message = f"{haters_name} {message}" if haters_name else message

            # Session setup with Cookie
            sess = requests.Session()
            sess.headers.update({
                'cookie': cookie,
                'user-agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36'
            })

            # Get security tokens from mbasic message page
            url = f"https://mbasic.facebook.com/messages/read/?tid={thread_id}"
            fb_dtsg, jazoest = get_fb_tokens(sess, url)

            if fb_dtsg:
                action_url = "https://mbasic.facebook.com/messages/send/?icm=1"
                data = {'fb_dtsg': fb_dtsg, 'jazoest': jazoest, 'body': full_message, 'send': 'Send'}
                res = sess.post(action_url, data=data)
                
                if res.status_code == 200:
                    capture_task_log(task_id, f"[+] SUCCESS: Msg {message_counter+1} sent to {thread_id}")
                else:
                    capture_task_log(task_id, f"[x] FAILED: Status {res.status_code}")
            else:
                capture_task_log(task_id, f"[!] COOKIE DEAD: Token extraction failed for cookie index {message_counter % max_cookies}")

            message_counter += 1
            time.sleep(speed)
        except Exception as e:
            capture_task_log(task_id, f"[!] ERROR: {str(e)}")
            time.sleep(speed)

def run_commenting_process(task_id, post_id, haters_name, speed, cookies, comments, owner_username):
    """Cookie based Commenting (Public Posts)"""
    num_comments = len(comments)
    max_cookies = len(cookies)
    comment_counter = 0 

    while TASK_MANAGER.get(task_id, {}).get('running', False):
        try:
            if TASK_MANAGER.get(task_id, {}).get('paused', False):
                time.sleep(1); continue
            
            cookie = cookies[comment_counter % max_cookies].strip()
            comment = comments[comment_counter % num_comments].strip()
            full_comment = f"{haters_name} {comment}" if haters_name else comment

            sess = requests.Session()
            sess.headers.update({
                'cookie': cookie,
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })

            # Get tokens from Post page
            url = f"https://mbasic.facebook.com/{post_id}"
            fb_dtsg, jazoest = get_fb_tokens(sess, url)

            if fb_dtsg:
                # Scrape the action URL for comment form (it changes)
                soup = BeautifulSoup(sess.get(url).text, 'html.parser')
                form = soup.find('form', action=lambda x: x and '/a/comment.php' in x)
                if form:
                    action = "https://mbasic.facebook.com" + form['action']
                    data = {'fb_dtsg': fb_dtsg, 'jazoest': jazoest, 'comment_text': full_comment}
                    res = sess.post(action, data=data)
                    capture_task_log(task_id, f"[+] SUCCESS: Comment {comment_counter+1} on Post {post_id}")
                else:
                    capture_task_log(task_id, "[x] Comment Form Not Found (Post Link Private?)")
            else:
                capture_task_log(task_id, "[!] COOKIE EXPIRED: Could not fetch fb_dtsg")

            comment_counter += 1
            time.sleep(speed)
        except Exception as e:
            capture_task_log(task_id, f"[!] ERROR: {str(e)}")
            time.sleep(speed)

# ==========================================================
# ROUTES (CORE SYSTEM)
# ==========================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    users = load_users()
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        if u in users and users[u]['password'] == p:
            if not users[u].get('is_approved'): return redirect(url_for('pending_approval'))
            session['username'] = u
            return redirect(url_for('menu_index'))
    return '''<body style="background:black;color:white;text-align:center;">
    <h2>MANI RAJPUT SERVER - LOGIN</h2>
    <form method="post"><input name="username" placeholder="User"><br><input name="password" type="password" placeholder="Pass"><br><input type="submit" value="Login"></form>
    <a href="/signup">Create ID</a></body>'''

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        users = load_users()
        users[u] = {"password":p, "is_approved":False, "is_admin":False, "tasks":[]}
        save_users(users)
        return "ID Created! Wait for Admin Approval."
    return '<form method="post"><input name="username" placeholder="New User"><br><input name="password" type="password"><br><input type="submit"></form>'

@app.route('/')
def menu_index():
    if 'username' not in session: return redirect(url_for('login'))
    return f'''<body style="background:black;color:yellow;text-align:center;">
    <h1>WELCOME {session['username']}</h1>
    <a href="/convo" style="color:white;display:block;margin:10px;">1. CONVO SERVER (COOKIES)</a>
    <a href="/post_comment" style="color:white;display:block;margin:10px;">2. POST COMMENTER (COOKIES)</a>
    <a href="/status" style="color:white;display:block;margin:10px;">3. CHECK STATUS</a>
    <a href="/logout">Logout</a></body>'''

@app.route('/convo', methods=['GET', 'POST'])
def convo_server():
    if 'username' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        # Cookie logic here
        tid = request.form.get('threadId')
        haters = request.form.get('kidx')
        speed = int(request.form.get('time'))
        
        cookie_data = request.form.get('cookiePaste')
        cookies = [c.strip() for c in cookie_data.splitlines() if c.strip()]
        
        msg_file = request.files.get('messagesFile')
        messages = [m.strip() for m in msg_file.read().decode().splitlines() if m.strip()]
        
        task_id = str(uuid.uuid4())
        t = threading.Thread(target=run_sending_process, args=(task_id, tid, haters, speed, cookies, messages, session['username']))
        t.daemon = True
        TASK_MANAGER[task_id] = {'running':True, 'paused':False, 'logs':[], 'name':f"CONVO-{tid}", 'owner':session['username']}
        t.start()
        return f"Task Started! ID: {task_id} <a href='/status'>Check Status</a>"

    return f'''<body style="background:black;color:white;padding:20px;">
    <h2>CONVO SERVER (COOKIE BASED)</h2>
    <form method="post" enctype="multipart/form-data">
        Thread ID: <input name="threadId" required><br><br>
        Cookies (Paste Each Line):<br>
        <textarea name="cookiePaste" rows="5" style="width:100%"></textarea><br><br>
        Message File: <input type="file" name="messagesFile" required><br><br>
        Hater Name: <input name="kidx"><br><br>
        Speed (Seconds): <input name="time" value="60"><br><br>
        <input type="submit" value="Start Sending">
    </form></body>'''

@app.route('/status')
def live_status():
    if 'username' not in session: return redirect(url_for('login'))
    # Filter tasks by owner
    out = ""
    for tid, info in TASK_MANAGER.items():
        if info['owner'] == session['username']:
            status = "Running" if info['running'] else "Stopped"
            out += f"<div style='border:1px solid white;margin:10px;padding:10px;'>Task: {info['name']} | Status: {status} <br> <a href='/view_task_log?task_id={tid}'>View Logs</a></div>"
    return f"<body style='background:black;color:green;'><h1>Tasks Status</h1>{out}<br><a href='/'>Back</a></body>"

@app.route('/view_task_log')
def view_task_log():
    tid = request.args.get('task_id')
    if tid in TASK_MANAGER:
        return "<body style='background:black;color:lime;'>" + "<br>".join(TASK_MANAGER[tid]['logs']) + "</body>"
    return "Not Found"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
