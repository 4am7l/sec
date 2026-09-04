from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
import hashlib
import string
import base64
from cryptography.fernet import Fernet
from supabase import create_client, Client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://shgxaxtjurbvbqdvmkzt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_FEE0CeWycaYbelk2VZPTBw_8j7lkftq")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    supabase = None

KEY_FILE = os.path.join(os.path.dirname(__file__), "secret.key")
def load_or_generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key
    with open(KEY_FILE, "rb") as f:
        return f.read()

SECRET_KEY = load_or_generate_key()
cipher = Fernet(SECRET_KEY)

def hash_data(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def generate_user_id():
    raw = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"#{raw}"

def generate_recovery_key():
    raw = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def send_to_user(self, recipient: str, message: dict):
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_json(message)

manager = ConnectionManager()

# --- BACKEND APIS ---
@app.post("/api/register")
async def register_user(data: dict):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection error")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    try:
        res = supabase.table("users").select("username").eq("username", username).execute()
        if res.data:
            raise HTTPException(status_code=400, detail="Username already exists")
        all_u = supabase.table("users").select("username").execute()
        assigned_role = "admin" if len(all_u.data) == 0 else "user"
        rec_key = generate_recovery_key()
        u_id = generate_user_id()
        payload = {
            "username": username,
            "password": hash_data(password),
            "recovery_key": hash_data(rec_key),
            "role": assigned_role,
            "user_id": u_id,
            "avatar": "",
            "status_text": "Available",
            "status_icon": "🟢 Online",
            "bio": "Hey there! I am using Secure Chat.",
            "friends": [],
            "friend_requests": [],
            "nicknames": {},
            "blocked": []
        }
        supabase.table("users").insert(payload).execute()
        return {"status": "success", "user_id": u_id, "recovery_key": rec_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
async def login_user(data: dict):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection error")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data or res.data[0]["password"] != hash_data(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "success", "user": res.data[0]}

@app.get("/api/get_user/{username}")
async def get_user_data(username: str):
    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "user": res.data[0]}

@app.get("/api/get_all_users")
async def get_all_users_api():
    res = supabase.table("users").select("username, user_id, bio, status_text, status_icon, avatar, friend_requests, friends").execute()
    return {"status": "success", "users": res.data}

@app.post("/api/update_user")
async def update_user(data: dict):
    username = data.get("username")
    updates = data.get("updates", {})
    supabase.table("users").update(updates).eq("username", username).execute()
    res = supabase.table("users").select("*").eq("username", username).execute()
    return {"status": "success", "user": res.data[0]}

# --- UI INTERFACE ---
FULL_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ CYBER MESSENGER</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: #090d16; color: #f1f5f9; display: flex; height: 100vh; overflow: hidden; }

        .auth-overlay { position: fixed; inset: 0; background: rgba(9, 13, 22, 0.96); backdrop-filter: blur(14px); display: flex; align-items: center; justify-content: center; z-index: 9999; }
        .auth-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); padding: 35px; border-radius: 20px; width: 440px; }
        .auth-card h1 { color: #3b82f6; font-size: 2.2em; font-weight: 800; text-align: center; }
        .auth-card p { color: #94a3b8; text-align: center; margin-bottom: 20px; }
        
        .auth-tabs { display: flex; gap: 8px; margin-bottom: 20px; background: #090d16; padding: 5px; border-radius: 12px; }
        .tab-btn { flex: 1; padding: 8px; background: transparent; border: none; color: #94a3b8; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .tab-btn.active { background: #2563eb; color: #fff; }

        .auth-form { display: none; }
        .auth-form.active { display: block; }
        .auth-form input { width: 100%; padding: 12px; margin-bottom: 12px; background: #090d16; border: 1px solid #334155; border-radius: 10px; color: #fff; outline: none; }
        .auth-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; }

        .sidebar { width: 310px; background: #111827; border-right: 1px solid rgba(255, 255, 255, 0.08); padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        .sidebar-profile { text-align: center; }
        .avatar-circle { width: 85px; height: 85px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #1e1b4b); color: #f8fafc; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #3b82f6; font-size: 32px; margin: 0 auto 10px auto; overflow: hidden; }
        .avatar-circle img { width: 100%; height: 100%; object-fit: cover; }
        
        .nav-btn { background: rgba(30, 41, 59, 0.4); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 12px 16px; text-align: left; font-size: 0.95em; font-weight: 600; width: 100%; cursor: pointer; margin-bottom: 6px; }
        .nav-btn:hover, .nav-btn.active { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; }

        .main-container { flex: 1; display: flex; flex-direction: column; background: #090d16; }
        .page-content { flex: 1; display: none; padding: 24px; overflow-y: auto; }
        .page-content.active { display: flex; flex-direction: column; }

        .st-tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 10px; }
        .st-tab-btn { background: rgba(30, 41, 59, 0.5); color: #94a3b8; border: none; padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .st-tab-btn.active { background: #2563eb; color: #fff; }

        .st-tab-content { display: none; }
        .st-tab-content.active { display: block; }

        .user-card { background: #111827; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 12px 16px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
        .card-box { background: #111827; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 22px; text-align: center; flex: 1; }

        .chat-header-bar { background: #111827; padding: 14px 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
        .chat-message-container { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 12px; background: #0b0f19; border-radius: 16px; }
        .msg-wrapper { display: flex; width: 100%; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }
        .insta-bubble { max-width: 68%; padding: 12px 16px; border-radius: 18px; font-size: 0.95em; line-height: 1.45; word-break: break-word; }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #ffffff; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; }

        .input-bar { background: #111827; padding: 14px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; gap: 10px; margin-top: 10px; }
        .input-bar textarea { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 10px 14px; color: #fff; outline: none; height: 45px; resize: none; font-size: 0.95em; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 20px; height: 45px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .attach-label { background: #1e293b; color: #94a3b8; border: 1px solid rgba(255,255,255,0.1); padding: 0 14px; height: 45px; border-radius: 12px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1.2em; }
    </style>
</head>
<body>

    <div class="auth-overlay" id="auth-modal">
        <div class="auth-card">
            <h1>⚡ CYBER MESSENGER</h1>
            <p>Encrypted Direct Messaging Platform</p>
            <div class="auth-tabs">
                <button class="tab-btn active" onclick="switchAuthTab('login')">🔑 LOGIN</button>
                <button class="tab-btn" onclick="switchAuthTab('reg')">📝 REGISTER</button>
            </div>
            <div class="auth-form active" id="form-login">
                <input type="text" id="l_u" placeholder="Username">
                <input type="password" id="l_p" placeholder="Password">
                <button class="auth-btn" onclick="apiLogin()">LOGIN 🚀</button>
            </div>
            <div class="auth-form" id="form-reg">
                <input type="text" id="r_u" placeholder="Username">
                <input type="password" id="r_p" placeholder="Password (8+ chars)">
                <button class="auth-btn" onclick="apiRegister()">CREATE ACCOUNT ✨</button>
            </div>
            <div id="auth-msg" style="margin-top:15px; font-size:0.85em; font-weight:bold;"></div>
        </div>
    </div>

    <div class="sidebar">
        <div class="sidebar-profile">
            <div class="avatar-circle" id="user-avatar-disp">👤</div>
            <h3 id="user-name-disp" style="color:#f8fafc; font-weight:700;">User</h3>
            <p id="user-status-disp" style="color: #60a5fa; font-size: 0.82em; margin-bottom: 6px;">"Available"</p>
            <span style="background:#2563eb; color:#ffffff; padding:3px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;" id="user-role-disp">USER</span>
        </div>
        <small style="color:#94a3b8;">Your Permanent ID:</small>
        <div style="background:#090d16; padding:8px; border-radius:8px; font-family:monospace; color:#3b82f6;" id="user-id-disp">#0000</div>
        <hr style="border:0.5px solid rgba(255,255,255,0.08); margin: 10px 0;">
        <button class="nav-btn active" onclick="showPage('dashboard', this)">🏠 Dashboard</button>
        <button class="nav-btn" onclick="showPage('messages', this)">💬 Messages</button>
        <button class="nav-btn" onclick="showPage('friends', this)">👥 Friends</button>
        <button class="nav-btn" onclick="showPage('profile', this)">👤 Profile</button>
        <button class="nav-btn" onclick="showPage('blocklist', this)">🚫 Blocklist</button>
        <button class="nav-btn" style="color:#ef4444;" onclick="location.reload()">🚪 Logout</button>
    </div>

    <div class="main-container">

        <div class="page-content active" id="page-dashboard">
            <h3>📊 System Overview</h3>
            <div style="display:flex; gap:15px; margin-top:15px;">
                <div class="card-box"><h2 style="color:#60a5fa; font-size:2em;" id="dash-friends-count">0</h2><small style="color:#94a3b8;">Active Friends</small></div>
                <div class="card-box"><h2 style="color:#f59e0b; font-size:2em;" id="dash-reqs-count">0</h2><small style="color:#94a3b8;">Pending Requests</small></div>
                <div class="card-box"><h2 style="color:#10b981; font-size:2em;">⚡</h2><small style="color:#94a3b8;">Cloud Database Active</small></div>
            </div>
        </div>

        <div class="page-content" id="page-messages">
            <div class="chat-header-bar">
                <div><strong id="target-disp-name">Select Friend to Chat</strong></div>
                <span style="background:#059669; color:#fff; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;">🔒 Encrypted</span>
            </div>
            <input type="text" id="target-user-input" placeholder="Recipient Username..." style="padding:10px; background:#111827; border:1px solid rgba(255,255,255,0.1); border-radius:8px; color:#fff; width:260px; outline:none; margin-bottom:10px;">
            
            <div class="chat-message-container" id="chat-box"></div>

            <div id="file-preview-name" style="font-size:0.8em; color:#60a5fa; margin-top:4px; display:none;"></div>

            <div class="input-bar">
                <label class="attach-label" for="file-input">📎</label>
                <input type="file" id="file-input" style="display:none;" onchange="handleFileSelect(this)">
                <textarea id="msg-input" placeholder="Write a message..." onkeydown="handleEnterKey(event)"></textarea>
                <button class="send-btn" onclick="sendMsg()">SEND 🚀</button>
            </div>
        </div>

        <div class="page-content" id="page-friends">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h3>👥 Friend Management</h3>
                <button class="auth-btn" style="width:auto; padding:6px 14px;" onclick="refreshUserData()">🔄 Refresh Data</button>
            </div>

            <div class="st-tabs">
                <button class="st-tab-btn active" onclick="switchStTab('search', this)">🔍 Search & Add</button>
                <button class="st-tab-btn" onclick="switchStTab('myfriends', this)">👥 My Friends</button>
                <button class="st-tab-btn" onclick="switchStTab('requests', this)">📩 Requests</button>
            </div>

            <div class="st-tab-content active" id="tab-search">
                <input type="text" id="s_query_key" placeholder="Search user by Username or ID (e.g. #A123)" style="width:100%; padding:10px; background:#111827; border:1px solid rgba(255,255,255,0.1); border-radius:8px; color:#fff; outline:none; margin-bottom:10px;" oninput="searchUsersLive()">
                <div id="search-results-list"></div>
            </div>

            <div class="st-tab-content" id="tab-myfriends">
                <div id="my-friends-tab-list"></div>
            </div>

            <div class="st-tab-content" id="tab-requests">
                <div id="requests-tab-list"></div>
            </div>
        </div>

        <div class="page-content" id="page-profile">
            <h3>👤 Profile Customization</h3>
            <div style="background:#111827; padding:20px; border-radius:12px; margin-top:15px;">
                <label style="font-size:0.85em; color:#94a3b8;">Custom Status Message</label>
                <input type="text" id="prof-status" style="width:100%; padding:10px; background:#090d16; border:1px solid #334155; border-radius:8px; color:#fff; margin-bottom:10px;">
                <label style="font-size:0.85em; color:#94a3b8;">About Me (Bio)</label>
                <textarea id="prof-bio" style="width:100%; padding:10px; background:#090d16; border:1px solid #334155; border-radius:8px; color:#fff; margin-bottom:10px;"></textarea>
                <button class="auth-btn" onclick="saveProfile()">SAVE PROFILE CHANGES 💾</button>
            </div>
        </div>

        <div class="page-content" id="page-blocklist">
            <h3>🚫 Blocklist Management</h3>
            <div id="blocklist-container" style="margin-top:15px;"></div>
        </div>

    </div>

    <script>
        let ws = null;
        let userData = null;
        let allUsersCache = [];
        let attachedFileData = null;

        function switchAuthTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            if(tab === 'login') {
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('form-login').classList.add('active');
            } else {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('form-reg').classList.add('active');
            }
        }

        async function apiLogin() {
            const u = document.getElementById('l_u').value.trim();
            const p = document.getElementById('l_p').value.trim();
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: u, password: p})
            });
            const data = await res.json();
            if(res.ok) initUserSession(data.user);
            else alert(data.detail);
        }

        async function apiRegister() {
            const u = document.getElementById('r_u').value.trim();
            const p = document.getElementById('r_p').value.trim();
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: u, password: p})
            });
            const data = await res.json();
            if(res.ok) alert(`Account created! ID: ${data.user_id} | Key: ${data.recovery_key}`);
            else alert(data.detail);
        }

        function initUserSession(user) {
            userData = user;
            updateUIProfile();
            document.getElementById('auth-modal').style.display = 'none';

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${userData.username}`);
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                appendBubble(data.sender, data.content, data.time, data.file);
            };
            refreshUserData();
        }

        async function refreshUserData() {
            const res = await fetch(`/api/get_user/${userData.username}`);
            const data = await res.json();
            if(res.ok) {
                userData = data.user;
                updateUIProfile();
            }
            const resAll = await fetch('/api/get_all_users');
            const dataAll = await resAll.json();
            if(resAll.ok) {
                allUsersCache = dataAll.users;
                renderFriendsTabs();
                renderBlocklist();
            }
        }

        function updateUIProfile() {
            document.getElementById('user-name-disp').innerText = userData.username;
            document.getElementById('user-status-disp').innerText = `"${userData.status_text || 'Available'}"`;
            document.getElementById('user-id-disp').innerText = userData.user_id || '#0000';
            document.getElementById('prof-status').value = userData.status_text || '';
            document.getElementById('prof-bio').value = userData.bio || '';

            const flist = userData.friends || [];
            const rlist = userData.friend_requests || [];
            document.getElementById('dash-friends-count').innerText = flist.length;
            document.getElementById('dash-reqs-count').innerText = rlist.length;
        }

        function switchStTab(tabId, btnEl) {
            document.querySelectorAll('.st-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.st-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            btnEl.classList.add('active');
        }

        function handleEnterKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMsg();
            }
        }

        function handleFileSelect(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                attachedFileData = {
                    name: file.name,
                    type: file.type,
                    base64: e.target.result
                };
                const prev = document.getElementById('file-preview-name');
                prev.innerText = `📁 Attached: ${file.name}`;
                prev.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }

        function sendMsg() {
            const input = document.getElementById("msg-input");
            const target = document.getElementById("target-user-input").value.trim();
            const msg = input.value.trim();

            if(!ws || ws.readyState !== WebSocket.OPEN) return alert("Session Disconnected! Please relogin.");
            if(!target) return alert("Please specify target username.");
            if(!msg && !attachedFileData) return;

            ws.send(JSON.stringify({
                recipient: target,
                message: msg,
                file: attachedFileData
            }));

            input.value = "";
            attachedFileData = null;
            document.getElementById('file-preview-name').style.display = 'none';
            document.getElementById('file-input').value = "";
        }

        function appendBubble(sender, content, time, file) {
            const isMine = (sender === userData.username);
            const chatBox = document.getElementById("chat-box");
            const wrapper = document.createElement("div");
            wrapper.className = "msg-wrapper " + (isMine ? "sent" : "received");

            let fileHtml = "";
            if (file) {
                if (file.type.startsWith("image/")) {
                    fileHtml = `<br><img src="${file.base64}" style="max-width:200px; border-radius:8px; margin-top:6px; display:block;">`;
                } else {
                    fileHtml = `<br><a href="${file.base64}" download="${file.name}" style="color:#60a5fa; font-size:0.85em; display:inline-block; margin-top:6px;">📄 Download ${file.name}</a>`;
                }
            }

            wrapper.innerHTML = `<div class="insta-bubble">${content || ''}${fileHtml}<span style="font-size:0.65em; display:block; opacity:0.7; text-align:right; margin-top:4px;">${time || 'NOW'}</span></div>`;
            chatBox.appendChild(wrapper);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function searchUsersLive() {
            const q = document.getElementById('s_query_key').value.trim().toLowerCase();
            const box = document.getElementById('search-results-list');
            box.innerHTML = "";
            if(!q) return;

            allUsersCache.forEach(u => {
                if(u.username !== userData.username && (u.username.toLowerCase().includes(q) || u.user_id.toLowerCase().includes(q))) {
                    const isFriend = (userData.friends || []).includes(u.username);
                    const isPending = (u.friend_requests || []).includes(userData.username);

                    let actionBtn = `<button class="auth-btn" style="width:auto; padding:6px 12px;" onclick="sendReq('${u.username}')">➕ Send Request</button>`;
                    if(isFriend) actionBtn = `<span style="color:#10b981; font-weight:bold;">Friends ✅</span>`;
                    else if(isPending) actionBtn = `<span style="color:#f59e0b; font-weight:bold;">Pending ⏳</span>`;

                    box.innerHTML += `
                    <div class="user-card">
                        <div>
                            <strong style="color:#f8fafc;">${u.username}</strong>
                            <span style="color:#60a5fa; font-size:0.88em; margin-left:6px;">(${u.user_id})</span>
                            <p style="color:#94a3b8; font-size:0.82em; margin:2px 0 0 0;">${u.bio || ''}</p>
                        </div>
                        <div>${actionBtn}</div>
                    </div>`;
                }
            });
        }

        async function sendReq(uname) {
            const uObj = allUsersCache.find(x => x.username === uname);
            let reqs = uObj.friend_requests || [];
            if(!reqs.includes(userData.username)) reqs.push(userData.username);

            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: uname, updates: {friend_requests: reqs}})
            });
            alert(`Request sent to ${uname}!`);
            refreshUserData();
        }

        function renderFriendsTabs() {
            const myfBox = document.getElementById('my-friends-tab-list');
            myfBox.innerHTML = "";
            const flist = userData.friends || [];
            if(flist.length === 0) myfBox.innerHTML = "<p style='color:#94a3b8;'>No friends added yet.</p>";
            else {
                flist.forEach(f => {
                    myfBox.innerHTML += `
                    <div class="user-card">
                        <div><strong style="color:#f8fafc;">${f}</strong></div>
                        <div style="display:flex; gap:6px;">
                            <button class="auth-btn" style="width:auto; padding:6px 12px;" onclick="startChat('${f}')">💬 Chat</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" onclick="unfriend('${f}')">🗑️ Unfriend</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" onclick="blockUser('${f}')">🚫 Block</button>
                        </div>
                    </div>`;
                });
            }

            const reqBox = document.getElementById('requests-tab-list');
            reqBox.innerHTML = "";
            const reqs = userData.friend_requests || [];
            if(reqs.length === 0) reqBox.innerHTML = "<p style='color:#94a3b8;'>No pending friend requests.</p>";
            else {
                reqs.forEach(r => {
                    reqBox.innerHTML += `
                    <div class="user-card">
                        <div><strong style="color:#f8fafc;">${r}</strong></div>
                        <div style="display:flex; gap:6px;">
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#059669;" onclick="acceptReq('${r}')">ACCEPT ✅</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" onclick="declineReq('${r}')">DECLINE ❌</button>
                        </div>
                    </div>`;
                });
            }
        }

        async function acceptReq(rUser) {
            let myF = userData.friends || [];
            let myR = userData.friend_requests || [];
            myF.push(rUser);
            myR = myR.filter(x => x !== rUser);

            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {friends: myF, friend_requests: myR}})
            });

            const rObj = allUsersCache.find(x => x.username === rUser);
            let rF = rObj ? (rObj.friends || []) : [];
            rF.push(userData.username);
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: rUser, updates: {friends: rF}})
            });

            refreshUserData();
        }

        async function declineReq(rUser) {
            let myR = (userData.friend_requests || []).filter(x => x !== rUser);
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {friend_requests: myR}})
            });
            refreshUserData();
        }

        async function unfriend(fUser) {
            let myF = (userData.friends || []).filter(x => x !== fUser);
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {friends: myF}})
            });
            refreshUserData();
        }

        async function blockUser(fUser) {
            let myB = userData.blocked || [];
            let myF = (userData.friends || []).filter(x => x !== fUser);
            if(!myB.includes(fUser)) myB.push(fUser);

            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {blocked: myB, friends: myF}})
            });
            refreshUserData();
        }

        function renderBlocklist() {
            const bBox = document.getElementById('blocklist-container');
            bBox.innerHTML = "";
            const blist = userData.blocked || [];
            if(blist.length === 0) bBox.innerHTML = "<p style='color:#94a3b8;'>No blocked users.</p>";
            else {
                blist.forEach(b => {
                    bBox.innerHTML += `
                    <div class="user-card">
                        <div><strong style="color:#f8fafc;">${b}</strong></div>
                        <button class="auth-btn" style="width:auto; padding:6px 12px; background:#059669;" onclick="unblock('${b}')">UNBLOCK ✅</button>
                    </div>`;
                });
            }
        }

        async function unblock(bUser) {
            let myB = (userData.blocked || []).filter(x => x !== bUser);
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {blocked: myB}})
            });
            refreshUserData();
        }

        function startChat(fname) {
            document.getElementById('target-user-input').value = fname;
            document.getElementById('target-disp-name').innerText = fname;
            showPage('messages', document.querySelectorAll('.nav-btn')[1]);
        }

        function showPage(pageId, btnEl) {
            document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            if(btnEl) btnEl.classList.add('active');
            if(pageId === 'friends' || pageId === 'blocklist') refreshUserData();
        }

        async function saveProfile() {
            const status_text = document.getElementById('prof-status').value;
            const bio = document.getElementById('prof-bio').value;

            const res = await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {status_text, bio}})
            });
            if(res.ok) {
                alert("Profile Saved!");
                refreshUserData();
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return FULL_UI_HTML

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            sender = username
            recipient = data.get("recipient")
            content = data.get("message")
            file = data.get("file")

            if (content or file) and recipient and supabase:
                enc_content = cipher.encrypt((content or "").encode()).decode()
                msg_id = secrets.token_hex(8)

                payload = {
                    "id": msg_id,
                    "sender": sender,
                    "recipient": recipient,
                    "content": enc_content,
                    "burn": False,
                    "reply": None,
                    "reactions": {}
                }
                supabase.table("messages").insert(payload).execute()

                msg_out = {
                    "id": msg_id,
                    "sender": sender,
                    "recipient": recipient,
                    "content": content,
                    "file": file,
                    "time": "NOW"
                }
                await manager.send_to_user(recipient, msg_out)
                await manager.send_to_user(sender, msg_out)

    except WebSocketDisconnect:
        manager.disconnect(username)
