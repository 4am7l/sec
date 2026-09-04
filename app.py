from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
import hashlib
import string
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

# --- FERNET ENCRYPTION ---
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

# --- WEBSOCKET MANAGER ---
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
        raise HTTPException(status_code=500, detail="خطأ في الاتصال بقاعدة البيانات")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="اسم المستخدم وكلمة السر مطلوبان")
    try:
        res = supabase.table("users").select("username").eq("username", username).execute()
        if res.data:
            raise HTTPException(status_code=400, detail="اسم المستخدم مستعمل سابقاً")
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
            "blocked": []
        }
        supabase.table("users").insert(payload).execute()
        return {"status": "success", "user_id": u_id, "recovery_key": rec_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
async def login_user(data: dict):
    if not supabase:
        raise HTTPException(status_code=500, detail="خطأ في الاتصال بقاعدة البيانات")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data or res.data[0]["password"] != hash_data(password):
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة السر غير صحيحة")
    return {"status": "success", "user": res.data[0]}

@app.get("/api/get_user/{username}")
async def get_user_data(username: str):
    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return {"status": "success", "user": res.data[0]}

@app.post("/api/update_profile")
async def update_profile(data: dict):
    username = data.get("username")
    status_text = data.get("status_text")
    bio = data.get("bio")
    avatar = data.get("avatar")
    
    update_data = {}
    if status_text is not None: update_data["status_text"] = status_text
    if bio is not None: update_data["bio"] = bio
    if avatar is not None: update_data["avatar"] = avatar
    
    supabase.table("users").update(update_data).eq("username", username).execute()
    res = supabase.table("users").select("*").eq("username", username).execute()
    return {"status": "success", "user": res.data[0]}

@app.get("/api/search_users")
async def search_users(q: str):
    res = supabase.table("users").select("username, user_id, bio, status_text, avatar").execute()
    matches = [u for u in res.data if q.lower() in u["username"].lower() or q.upper() in u.get("user_id", "")]
    return {"status": "success", "users": matches}

# --- FRIENDS & BLOCK SYSTEM ---
@app.post("/api/send_request")
async def send_request(data: dict):
    username = data.get("username")
    target_name = data.get("target_name")
    
    res = supabase.table("users").select("friend_requests").eq("username", target_name).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        
    reqs = res.data[0].get("friend_requests") or []
    if username not in reqs:
        reqs.append(username)
        supabase.table("users").update({"friend_requests": reqs}).eq("username", target_name).execute()
        
    return {"status": "success"}

@app.post("/api/respond_request")
async def respond_request(data: dict):
    username = data.get("username")
    requester = data.get("requester")
    action = data.get("action")
    
    u_data = supabase.table("users").select("friends, friend_requests").eq("username", username).execute().data[0]
    reqs = u_data.get("friend_requests") or []
    friends = u_data.get("friends") or []
    
    if requester in reqs:
        reqs.remove(requester)
        
    if action == "accept":
        if requester not in friends:
            friends.append(requester)
        r_data = supabase.table("users").select("friends").eq("username", requester).execute().data[0]
        r_friends = r_data.get("friends") or []
        if username not in r_friends:
            r_friends.append(username)
            supabase.table("users").update({"friends": r_friends}).eq("username", requester).execute()

    supabase.table("users").update({"friends": friends, "friend_requests": reqs}).eq("username", username).execute()
    return {"status": "success"}

@app.post("/api/block_user")
async def block_user(data: dict):
    username = data.get("username")
    target_name = data.get("target_name")
    action = data.get("action") # "block" or "unblock"

    u_data = supabase.table("users").select("friends, blocked").eq("username", username).execute().data[0]
    friends = u_data.get("friends") or []
    blocked = u_data.get("blocked") or []

    if action == "block":
        if target_name not in blocked:
            blocked.append(target_name)
        if target_name in friends:
            friends.remove(target_name)
    elif action == "unblock":
        if target_name in blocked:
            blocked.remove(target_name)

    supabase.table("users").update({"friends": friends, "blocked": blocked}).eq("username", username).execute()
    return {"status": "success"}

# --- FULL REALTIME INTERFACE ---
FULL_UI_HTML = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ CYBER MESSENGER</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: #090d16; color: #f1f5f9; display: flex; height: 100vh; overflow: hidden; }

        .auth-overlay { position: fixed; inset: 0; background: rgba(9, 13, 22, 0.96); backdrop-filter: blur(14px); display: flex; align-items: center; justify-content: center; z-index: 9999; }
        .auth-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); padding: 35px; border-radius: 20px; width: 440px; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
        .auth-card h1 { color: #3b82f6; font-size: 2.2em; font-weight: 800; text-align: center; margin-bottom: 2px; }
        .auth-card p.subtitle { color: #94a3b8; font-size: 0.9em; text-align: center; margin-bottom: 20px; }
        
        .auth-tabs { display: flex; gap: 8px; margin-bottom: 20px; background: #090d16; padding: 5px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); }
        .tab-btn { flex: 1; padding: 8px; background: transparent; border: none; color: #94a3b8; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 0.85em; }
        .tab-btn.active { background: #2563eb; color: #fff; }

        .auth-form { display: none; }
        .auth-form.active { display: block; }
        .auth-form input { width: 100%; padding: 12px; margin-bottom: 12px; background: #090d16; border: 1px solid #334155; border-radius: 10px; color: #fff; outline: none; font-size: 0.9em; }
        .auth-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; transition: all 0.2s; }

        .sidebar { width: 310px; background: #111827; border-right: 1px solid rgba(255, 255, 255, 0.08); padding: 20px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
        .sidebar-profile { text-align: center; padding: 10px 0; }
        .avatar-circle { width: 85px; height: 85px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #1e1b4b); color: #f8fafc; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #3b82f6; font-size: 32px; margin-bottom: 10px; overflow: hidden; }
        .avatar-circle img { width: 100%; height: 100%; object-fit: cover; }
        .role-badge { background: #2563eb; color: #ffffff; padding: 3px 10px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
        
        .nav-btn { background: rgba(30, 41, 59, 0.4); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 12px 16px; text-align: left; font-size: 0.95em; font-weight: 600; width: 100%; cursor: pointer; display: flex; align-items: center; gap: 10px; transition: all 0.25s ease; margin-bottom: 6px; }
        .nav-btn:hover, .nav-btn.active { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; }

        .main-container { flex: 1; display: flex; flex-direction: column; background: #090d16; }
        .page-content { flex: 1; display: none; padding: 24px; overflow-y: auto; }
        .page-content.active { display: flex; flex-direction: column; }

        .card-box { background: #111827; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 22px; text-align: center; flex: 1; }
        .form-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); padding: 20px; border-radius: 16px; margin-top: 15px; }
        .form-card input, .form-card textarea { width: 100%; padding: 10px; background: #090d16; border: 1px solid #334155; border-radius: 8px; color: #fff; margin-bottom: 10px; outline: none; }
        .user-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
        
        .section-tabs { display: flex; gap: 10px; margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 10px; }
        .sec-tab-btn { background: rgba(30, 41, 59, 0.5); color: #94a3b8; border: none; padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .sec-tab-btn.active { background: #2563eb; color: #fff; }

        .sec-sub-page { display: none; }
        .sec-sub-page.active { display: block; }

        .chat-header-bar { background: #111827; padding: 14px 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
        .chat-message-container { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 8px; border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; background: #0b0f19; }
        .msg-wrapper { display: flex; width: 100%; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }
        .insta-bubble { max-width: 68%; padding: 12px 16px; border-radius: 18px; font-size: 0.95em; line-height: 1.45; word-wrap: break-word; }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #ffffff; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; }
        .input-bar { background: #111827; padding: 16px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; margin-top: 10px; }
        .input-bar textarea { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px; color: #fff; outline: none; height: 50px; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 24px; border-radius: 12px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>

    <div class="auth-overlay" id="auth-modal">
        <div class="auth-card">
            <h1>⚡ CYBER MESSENGER</h1>
            <p class="subtitle">Direct Encrypted Platform</p>
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
            <span class="role-badge" id="user-role-disp">USER</span>
        </div>
        <small style="color:#94a3b8;">Your Permanent ID:</small>
        <div style="background:#090d16; padding:8px; border-radius:8px; font-family:monospace; color:#3b82f6;" id="user-id-disp">#0000</div>
        <hr style="border:0.5px solid rgba(255,255,255,0.08); margin: 10px 0;">
        <button class="nav-btn active" onclick="showPage('dashboard', this)">🏠 Dashboard</button>
        <button class="nav-btn" onclick="showPage('messages', this)">💬 Messages</button>
        <button class="nav-btn" onclick="showPage('friends', this)">👥 Friends Hub</button>
        <button class="nav-btn" onclick="showPage('profile', this)">👤 Profile</button>
        <button class="nav-btn" style="color:#ef4444;" onclick="location.reload()">🚪 Logout</button>
    </div>

    <div class="main-container">

        <div class="page-content active" id="page-dashboard">
            <h3>📊 Dashboard Overview</h3>
            <div style="display:flex; gap:15px; margin-top:15px;">
                <div class="card-box"><h2 style="color:#60a5fa; font-size:2em;" id="dash-friends-count">0</h2><small style="color:#94a3b8;">Active Friends</small></div>
                <div class="card-box"><h2 style="color:#f59e0b; font-size:2em;" id="dash-reqs-count">0</h2><small style="color:#94a3b8;">Pending Requests</small></div>
                <div class="card-box"><h2 style="color:#10b981; font-size:2em;">⚡</h2><small style="color:#94a3b8;">WebSocket Active</small></div>
            </div>
        </div>

        <div class="page-content" id="page-messages">
            <div class="chat-header-bar">
                <div><strong id="target-disp-name">Select Friend to Chat</strong></div>
                <span style="background:#059669; color:#fff; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;">🔒 Encrypted</span>
            </div>
            <input type="text" id="target-user-input" placeholder="Recipient Username..." style="padding:10px; background:#111827; border:1px solid rgba(255,255,255,0.1); border-radius:8px; color:#fff; width:260px; outline:none; margin-bottom:10px;">
            <div class="chat-message-container" id="chat-box"></div>
            <div class="input-bar">
                <textarea id="msg-input" placeholder="Message..."></textarea>
                <button class="send-btn" onclick="sendMsg()">SEND 🚀</button>
            </div>
        </div>

        <div class="page-content" id="page-profile">
            <h3>👤 Profile Customization</h3>
            <div class="form-card">
                <label style="font-size:0.85em; color:#94a3b8;">Status Message</label>
                <input type="text" id="prof-status">
                <label style="font-size:0.85em; color:#94a3b8;">About Me (Bio)</label>
                <textarea id="prof-bio"></textarea>
                <label style="font-size:0.85em; color:#94a3b8;">Avatar URL (Image Link)</label>
                <input type="text" id="prof-avatar">
                <button class="auth-btn" style="width:100%;" onclick="saveProfile()">Save Profile 💾</button>
            </div>
        </div>

        <!-- COMPLETE FRIENDS HUB SECTION -->
        <div class="page-content" id="page-friends">
            <h3>👥 Friends Hub</h3>
            
            <div class="section-tabs" style="margin-top:15px;">
                <button class="sec-tab-btn active" onclick="switchFriendsTab('list', this)">👥 My Friends</button>
                <button class="sec-tab-btn" onclick="switchFriendsTab('reqs', this)">📩 Requests</button>
                <button class="sec-tab-btn" onclick="switchFriendsTab('search', this)">🔍 Search Users</button>
                <button class="sec-tab-btn" onclick="switchFriendsTab('blocked', this)">🚫 Blocked Users</button>
            </div>

            <!-- TAB 1: FRIENDS LIST -->
            <div class="sec-sub-page active" id="sub-friends-list">
                <div class="form-card">
                    <h4>My Active Friends</h4>
                    <div id="my-friends-container" style="margin-top:10px;"></div>
                </div>
            </div>

            <!-- TAB 2: PENDING REQUESTS -->
            <div class="sec-sub-page" id="sub-friends-reqs">
                <div class="form-card">
                    <h4>Pending Friend Requests</h4>
                    <div id="pending-requests-container" style="margin-top:10px;"></div>
                </div>
            </div>

            <!-- TAB 3: SEARCH & ADD -->
            <div class="sec-sub-page" id="sub-friends-search">
                <div class="form-card">
                    <h4>Search Users by Name or ID</h4>
                    <input type="text" id="friend-search-q" placeholder="Type Username or #ID..." style="margin-top:8px;">
                    <button class="auth-btn" style="width:100%;" onclick="searchFriends()">Search 🔍</button>
                    <div id="search-results-container" style="margin-top:15px;"></div>
                </div>
            </div>

            <!-- TAB 4: BLOCKED USERS -->
            <div class="sec-sub-page" id="sub-friends-blocked">
                <div class="form-card">
                    <h4>Blocked List</h4>
                    <div id="blocked-users-container" style="margin-top:10px;"></div>
                </div>
            </div>
        </div>

    </div>

    <script>
        let ws = null;
        let userData = null;

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
            if(res.ok) alert(`SUCCESS! Saved Recovery Key: ${data.recovery_key}`);
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
                appendBubble(data.sender, data.content, data.time);
            };
            refreshUserData();
        }

        async function refreshUserData() {
            const res = await fetch(`/api/get_user/${userData.username}`);
            const data = await res.json();
            if(res.ok) {
                userData = data.user;
                updateUIProfile();
                renderAllFriendsHubData();
            }
        }

        function updateUIProfile() {
            document.getElementById('user-name-disp').innerText = userData.username;
            document.getElementById('user-status-disp').innerText = `"${userData.status_text || 'Available'}"`;
            document.getElementById('user-id-disp').innerText = userData.user_id || '#0000';
            document.getElementById('prof-status').value = userData.status_text || '';
            document.getElementById('prof-bio').value = userData.bio || '';
            document.getElementById('prof-avatar').value = userData.avatar || '';

            const flist = userData.friends || [];
            const rlist = userData.friend_requests || [];
            document.getElementById('dash-friends-count').innerText = flist.length;
            document.getElementById('dash-reqs-count').innerText = rlist.length;

            if(userData.avatar) {
                document.getElementById('user-avatar-disp').innerHTML = `<img src="${userData.avatar}">`;
            } else {
                document.getElementById('user-avatar-disp').innerText = userData.username.charAt(0).toUpperCase();
            }
        }

        async function saveProfile() {
            const status_text = document.getElementById('prof-status').value;
            const bio = document.getElementById('prof-bio').value;
            const avatar = document.getElementById('prof-avatar').value;

            const res = await fetch('/api/update_profile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, status_text, bio, avatar})
            });
            const data = await res.json();
            if(res.ok) {
                userData = data.user;
                updateUIProfile();
                alert("Profile Saved!");
            }
        }

        function switchFriendsTab(tabName, btnEl) {
            document.querySelectorAll('.sec-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.sec-sub-page').forEach(p => p.classList.remove('active'));

            document.getElementById('sub-friends-' + tabName).classList.add('active');
            btnEl.classList.add('active');
        }

        async function searchFriends() {
            const q = document.getElementById('friend-search-q').value.trim();
            if(!q) return;
            const res = await fetch(`/api/search_users?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            const box = document.getElementById('search-results-container');
            box.innerHTML = "";
            data.users.forEach(u => {
                if(u.username !== userData.username) {
                    const isFriend = (userData.friends || []).includes(u.username);
                    box.innerHTML += `
                    <div class="user-card">
                        <div>
                            <strong>${u.username}</strong> (${u.user_id})
                            <p style="font-size:0.8em; color:#94a3b8;">${u.bio || ''}</p>
                        </div>
                        ${isFriend ? '<span style="color:#10b981; font-weight:bold;">Friend ✅</span>' : `<button class="auth-btn" style="width:auto; padding:6px 12px;" onclick="sendRequest('${u.username}')">📩 Send Request</button>`}
                    </div>`;
                }
            });
        }

        async function sendRequest(tname) {
            const res = await fetch('/api/send_request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, target_name: tname})
            });
            if(res.ok) alert("Request Sent!");
        }

        function renderAllFriendsHubData() {
            // 1. Render Friends
            const fBox = document.getElementById('my-friends-container');
            fBox.innerHTML = "";
            const flist = userData.friends || [];
            if(flist.length === 0) fBox.innerHTML = "<p style='color:#94a3b8;'>No friends added yet.</p>";
            else {
                flist.forEach(f => {
                    fBox.innerHTML += `
                    <div class="user-card">
                        <div><strong>${f}</strong></div>
                        <div>
                            <button class="auth-btn" style="width:auto; padding:6px 12px;" onclick="startChat('${f}')">💬 Chat</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" onclick="blockUser('${f}', 'block')">🚫 Block</button>
                        </div>
                    </div>`;
                });
            }

            // 2. Render Pending Requests
            const rBox = document.getElementById('pending-requests-container');
            rBox.innerHTML = "";
            const reqs = userData.friend_requests || [];
            if(reqs.length === 0) rBox.innerHTML = "<p style='color:#94a3b8;'>No pending requests.</p>";
            else {
                reqs.forEach(r => {
                    rBox.innerHTML += `
                    <div class="user-card">
                        <div><strong>${r}</strong> sent you a request</div>
                        <div>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#059669;" onclick="respondReq('${r}', 'accept')">Accept ✅</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" onclick="respondReq('${r}', 'decline')">Decline ❌</button>
                        </div>
                    </div>`;
                });
            }

            // 3. Render Blocked Users
            const bBox = document.getElementById('blocked-users-container');
            bBox.innerHTML = "";
            const blist = userData.blocked || [];
            if(blist.length === 0) bBox.innerHTML = "<p style='color:#94a3b8;'>No blocked users.</p>";
            else {
                blist.forEach(b => {
                    bBox.innerHTML += `
                    <div class="user-card">
                        <div><strong>${b}</strong></div>
                        <button class="auth-btn" style="width:auto; padding:6px 12px; background:#059669;" onclick="blockUser('${b}', 'unblock')">Unblock ✅</button>
                    </div>`;
                });
            }
        }

        async function respondReq(reqName, action) {
            const res = await fetch('/api/respond_request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, requester: reqName, action: action})
            });
            if(res.ok) refreshUserData();
        }

        async function blockUser(tname, action) {
            const res = await fetch('/api/block_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, target_name: tname, action: action})
            });
            if(res.ok) refreshUserData();
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
            if(pageId === 'friends') refreshUserData();
        }

        function sendMsg() {
            const input = document.getElementById("msg-input");
            const target = document.getElementById("target-user-input").value.trim();
            const msg = input.value.trim();
            if(!ws || ws.readyState !== WebSocket.OPEN) return alert("Not Connected");
            if(!msg || !target) return alert("Specify recipient & message");
            ws.send(JSON.stringify({ recipient: target, message: msg }));
            input.value = "";
        }

        function appendBubble(sender, content, time) {
            const isMine = (sender === userData.username);
            const chatBox = document.getElementById("chat-box");
            const wrapper = document.createElement("div");
            wrapper.className = "msg-wrapper " + (isMine ? "sent" : "received");
            wrapper.innerHTML = `<div class="insta-bubble">${content}<span class="msg-time" style="font-size:0.65em; display:block; opacity:0.7;">${time || 'NOW'}</span></div>`;
            chatBox.appendChild(wrapper);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
