from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
import os
import secrets
import hashlib
import string
from cryptography.fernet import Fernet
from supabase import create_client, Client

app = FastAPI()

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://shgxaxtjurbvbqdvmkzt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_FEE0CeWycaYbelk2VZPTBw_8j7lkftq")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

# --- DATABASE AUTH APIs ---
@app.post("/api/register")
async def register_user(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="اسم المستخدم وكلمة السر مطلوبان")
    
    res = supabase.table("users").select("*").eq("username", username).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="اسم المستخدم مستعمل سابقاً في قاعدة البيانات")
    
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

@app.post("/api/login")
async def login_user(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="يرجى إدخال اسم المستخدم وكلمة السر")

    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="الحساب غير موجود في قاعدة البيانات")
    
    user_row = res.data[0]
    if user_row["password"] != hash_data(password):
        raise HTTPException(status_code=401, detail="كلمة السر غير صحيحة")
    
    return {"status": "success", "user": user_row}

@app.post("/api/recover")
async def recover_password(data: dict):
    username = data.get("username", "").strip()
    rec_key = data.get("recovery_key", "").strip()
    new_pass = data.get("new_password", "").strip()
    
    if not username or not rec_key or not new_pass:
        raise HTTPException(status_code=400, detail="جميع الحقول مطلوبة")

    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="اسم المستخدم غير موجود")
    
    user_row = res.data[0]
    if user_row.get("recovery_key") != hash_data(rec_key):
        raise HTTPException(status_code=401, detail="مفتاح الاستعادة (Recovery Key) غير صحيح")
    
    supabase.table("users").update({"password": hash_data(new_pass)}).eq("username", username).execute()
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

        /* Auth Gateway Glassmorphism */
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
        .auth-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); }

        /* Sidebar UI */
        .sidebar { width: 310px; background: #111827; border-right: 1px solid rgba(255, 255, 255, 0.08); padding: 20px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
        .sidebar-profile { text-align: center; padding: 10px 0; }
        .avatar-circle { width: 85px; height: 85px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #1e1b4b); color: #f8fafc; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #3b82f6; font-size: 32px; margin-bottom: 10px; }
        .role-badge { background: #2563eb; color: #ffffff; padding: 3px 10px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
        
        .nav-section-title { color: #60a5fa; font-size: 0.75em; font-weight: bold; letter-spacing: 1px; margin-top: 15px; margin-bottom: 5px; }
        .nav-btn { background: rgba(30, 41, 59, 0.4); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 12px 16px; text-align: left; font-size: 0.95em; font-weight: 600; width: 100%; cursor: pointer; display: flex; align-items: center; gap: 10px; transition: all 0.25s ease; margin-bottom: 6px; }
        .nav-btn:hover, .nav-btn.active { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; border-color: rgba(255, 255, 255, 0.2); box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); }

        /* Main Workspace */
        .main-container { flex: 1; display: flex; flex-direction: column; background: #090d16; }
        .page-content { flex: 1; display: none; padding: 24px; overflow-y: auto; }
        .page-content.active { display: flex; flex-direction: column; }

        /* Chat UI */
        .chat-header-bar { background: #111827; padding: 14px 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
        .chat-message-container { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 8px; border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; background: #0b0f19; }
        
        .msg-wrapper { display: flex; width: 100%; margin-bottom: 2px; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }
        
        .insta-bubble { max-width: 68%; padding: 12px 16px; border-radius: 18px; font-size: 0.95em; line-height: 1.45; word-wrap: break-word; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25); }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #ffffff; border-bottom-right-radius: 4px; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; border-bottom-left-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.05); }
        .msg-time { font-size: 0.68em; opacity: 0.75; display: block; text-align: right; margin-top: 4px; }

        .card-box { background: #111827; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 22px; text-align: center; flex: 1; }
        .input-bar { background: #111827; padding: 16px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; margin-top: 10px; }
        .input-bar textarea { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px; color: #fff; outline: none; resize: none; height: 50px; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 24px; border-radius: 12px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>

    <!-- AUTH GATEWAY MODAL -->
    <div class="auth-overlay" id="auth-modal">
        <div class="auth-card">
            <h1>⚡ CYBER MESSENGER</h1>
            <p class="subtitle">Encrypted Direct Messaging Platform</p>
            
            <div class="auth-tabs">
                <button class="tab-btn active" onclick="switchAuthTab('login')">🔑 LOGIN</button>
                <button class="tab-btn" onclick="switchAuthTab('reg')">📝 REGISTER</button>
                <button class="tab-btn" onclick="switchAuthTab('rec')">🛠️ RECOVERY</button>
            </div>

            <!-- LOGIN -->
            <div class="auth-form active" id="form-login">
                <input type="text" id="l_u" placeholder="Username">
                <input type="password" id="l_p" placeholder="Password">
                <button class="auth-btn" onclick="apiLogin()">LOGIN 🚀</button>
            </div>

            <!-- REGISTER -->
            <div class="auth-form" id="form-reg">
                <input type="text" id="r_u" placeholder="Username">
                <input type="password" id="r_p" placeholder="Password (8+ chars)">
                <button class="auth-btn" onclick="apiRegister()">CREATE ACCOUNT ✨</button>
            </div>

            <!-- RECOVERY -->
            <div class="auth-form" id="form-rec">
                <input type="text" id="rec_u" placeholder="Username">
                <input type="text" id="rec_k" placeholder="Recovery Key (XXXX-XXXX)">
                <input type="password" id="rec_p" placeholder="New Password">
                <button class="auth-btn" onclick="apiRecover()">RESET PASSWORD 🔐</button>
            </div>

            <div id="auth-msg" style="margin-top:15px; font-size:0.85em; font-weight:bold; word-break:break-all;"></div>
        </div>
    </div>

    <!-- SIDEBAR -->
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
        <div class="nav-section-title">NAVIGATION MENU</div>

        <button class="nav-btn active" onclick="showPage('dashboard', this)">🏠 Dashboard</button>
        <button class="nav-btn" onclick="showPage('messages', this)">💬 Messages</button>
        <button class="nav-btn" onclick="showPage('friends', this)">👥 Friends</button>
        <button class="nav-btn" onclick="showPage('profile', this)">👤 Profile</button>
        <button class="nav-btn" onclick="showPage('blocklist', this)">🚫 Blocklist</button>
        <button class="nav-btn" onclick="showPage('settings', this)">⚙️ Settings</button>
        
        <hr style="border:0.5px solid rgba(255,255,255,0.08); margin: 10px 0;">
        <button class="nav-btn" style="color:#ef4444;" onclick="location.reload()">🚪 Logout</button>
    </div>

    <!-- MAIN DISPLAY AREAS -->
    <div class="main-container">

        <!-- DASHBOARD -->
        <div class="page-content active" id="page-dashboard">
            <h3 style="margin-bottom:20px;">📊 System Overview</h3>
            <div style="display:flex; gap:15px; margin-bottom:20px;">
                <div class="card-box"><h2 style="color:#60a5fa; font-size:2.2em;" id="dash-friends-count">0</h2><small style="color:#94a3b8;">Active Friends</small></div>
                <div class="card-box"><h2 style="color:#f59e0b; font-size:2.2em;" id="dash-reqs-count">0</h2><small style="color:#94a3b8;">Pending Requests</small></div>
                <div class="card-box"><h2 style="color:#10b981; font-size:2.2em;">⚡</h2><small style="color:#94a3b8;">Database Direct Active</small></div>
            </div>
            <button class="auth-btn" style="width: auto; padding: 12px 24px;" onclick="showPage('messages', document.querySelectorAll('.nav-btn')[1])">💬 Open Chat Room</button>
        </div>

        <!-- MESSAGES -->
        <div class="page-content" id="page-messages">
            <div class="chat-header-bar">
                <div style="display:flex; align-items:center; gap:14px;">
                    <div style="font-size:1.5em;">👤</div>
                    <div>
                        <strong id="target-disp-name" style="font-size: 1.2em; color:#f8fafc;">Direct Encrypted Chat</strong>
                        <small style="display:block; color:#94a3b8;">Realtime WebSocket</small>
                    </div>
                </div>
                <span style="background:#059669; color:#ffffff; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;">🔒 Encrypted</span>
            </div>

            <div style="margin-bottom:10px;">
                <input type="text" id="target-user-input" placeholder="Recipient Username..." style="padding:10px; background:#111827; border:1px solid rgba(255,255,255,0.1); border-radius:8px; color:#fff; width:260px; outline:none;">
            </div>

            <div class="chat-message-container" id="chat-box"></div>

            <div class="input-bar">
                <textarea id="msg-input" placeholder="Message..."></textarea>
                <button class="send-btn" onclick="sendMsg()">SEND 🚀</button>
            </div>
        </div>

        <!-- FRIENDS -->
        <div class="page-content" id="page-friends">
            <h3>👥 Friend Management</h3>
            <p style="color:#94a3b8; margin-top:10px;">Search users or manage requests...</p>
        </div>

        <!-- PROFILE -->
        <div class="page-content" id="page-profile">
            <h3>👤 Profile Customization</h3>
            <p style="color:#94a3b8; margin-top:10px;">Status and Bio customization ready.</p>
        </div>

        <!-- BLOCKLIST -->
        <div class="page-content" id="page-blocklist">
            <h3>🚫 Blocklist Management</h3>
            <p style="color:#94a3b8; margin-top:10px;">No blocked users.</p>
        </div>

        <!-- SETTINGS -->
        <div class="page-content" id="page-settings">
            <h3>⚙️ Account Security Settings</h3>
            <p style="color:#94a3b8; margin-top:10px;">Security and keys status: ACTIVE</p>
        </div>

    </div>

    <script>
        let ws = null;
        let currentUser = null;

        function switchAuthTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            if(tab === 'login') {
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('form-login').classList.add('active');
            } else if(tab === 'reg') {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('form-reg').classList.add('active');
            } else {
                document.querySelectorAll('.tab-btn')[2].classList.add('active');
                document.getElementById('form-rec').classList.add('active');
            }
            const msgEl = document.getElementById('auth-msg');
            msgEl.innerText = "";
        }

        async function apiLogin() {
            const u = document.getElementById('l_u').value.trim();
            const p = document.getElementById('l_p').value.trim();
            const msgEl = document.getElementById('auth-msg');
            msgEl.style.color = "#ef4444";

            if(!u || !p) {
                msgEl.innerText = "يرجى كتابة اسم المستخدم وكلمة السر";
                return;
            }

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                if(res.ok && data.status === "success") {
                    initUserSession(data.user);
                } else {
                    msgEl.innerText = data.detail || "فشل تسجيل الدخول";
                }
            } catch(e) {
                msgEl.innerText = "خطأ في الاتصال بالسيرفر";
            }
        }

        async function apiRegister() {
            const u = document.getElementById('r_u').value.trim();
            const p = document.getElementById('r_p').value.trim();
            const msgEl = document.getElementById('auth-msg');

            if(!u || !p) {
                msgEl.style.color = "#ef4444";
                msgEl.innerText = "يرجى كتابة اسم المستخدم وكلمة السر";
                return;
            }

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                if(res.ok && data.status === "success") {
                    msgEl.style.color = "#10b981";
                    msgEl.innerText = `تم إنشاء الحساب! ID: ${data.user_id} | احفظ مفتاح الاستعادة: ${data.recovery_key}`;
                } else {
                    msgEl.style.color = "#ef4444";
                    msgEl.innerText = data.detail || "فشل إنشاء الحساب";
                }
            } catch(e) {
                msgEl.style.color = "#ef4444";
                msgEl.innerText = "خطأ في الاتصال بالسيرفر";
            }
        }

        async function apiRecover() {
            const u = document.getElementById('rec_u').value.trim();
            const k = document.getElementById('rec_k').value.trim();
            const p = document.getElementById('rec_p').value.trim();
            const msgEl = document.getElementById('auth-msg');

            try {
                const res = await fetch('/api/recover', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, recovery_key: k, new_password: p})
                });
                const data = await res.json();
                if(res.ok && data.status === "success") {
                    msgEl.style.color = "#10b981";
                    msgEl.innerText = "تم إعادة تعيين كلمة السر بنجاح! يمكنك الآن تسجيل الدخول.";
                } else {
                    msgEl.style.color = "#ef4444";
                    msgEl.innerText = data.detail || "فشلت عملية الاستعادة";
                }
            } catch(e) {
                msgEl.style.color = "#ef4444";
                msgEl.innerText = "خطأ في الاتصال بالسيرفر";
            }
        }

        function initUserSession(userRow) {
            currentUser = userRow.username;
            document.getElementById('user-name-disp').innerText = currentUser;
            document.getElementById('user-avatar-disp').innerText = currentUser.charAt(0).toUpperCase();
            document.getElementById('user-status-disp').innerText = `"${userRow.status_text || 'Available'}"`;
            document.getElementById('user-role-disp').innerText = (userRow.role || 'USER').toUpperCase();
            document.getElementById('user-id-disp').innerText = userRow.user_id || '#0000';
            
            document.getElementById('dash-friends-count').innerText = (userRow.friends || []).length;
            document.getElementById('dash-reqs-count').innerText = (userRow.friend_requests || []).length;

            document.getElementById('auth-modal').style.display = 'none';

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${currentUser}`);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                appendBubble(data.sender, data.content, data.time);
            };
        }

        function showPage(pageId, btnEl) {
            document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById('page-' + pageId).classList.add('active');
            if(btnEl) btnEl.classList.add('active');
        }

        function sendMsg() {
            const input = document.getElementById("msg-input");
            const target = document.getElementById("target-user-input").value.trim();
            const msg = input.value.trim();

            if(!ws || ws.readyState !== WebSocket.OPEN) return alert("الجلسة غير متصلة");
            if(!msg || !target) return alert("حدد المستخدم المستلم واكتب الرسالة");

            ws.send(JSON.stringify({ recipient: target, message: msg }));
            input.value = "";
        }

        function appendBubble(sender, content, time) {
            const isMine = (sender === currentUser);
            const chatBox = document.getElementById("chat-box");
            const wrapper = document.createElement("div");
            wrapper.className = "msg-wrapper " + (isMine ? "sent" : "received");
            wrapper.innerHTML = `<div class="insta-bubble">${content}<span class="msg-time">${time || 'NOW'}</span></div>`;
            chatBox.appendChild(wrapper);
            chatBox.scrollTop = chatBox.scrollHeight;
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

            if content and recipient:
                enc_content = cipher.encrypt(content.encode()).decode()
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
                    "time": "NOW"
                }
                await manager.send_to_user(recipient, msg_out)
                await manager.send_to_user(sender, msg_out)

    except WebSocketDisconnect:
        manager.disconnect(username)
