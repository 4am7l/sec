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

FIXED_SECRET_KEY = os.environ.get("FERNET_KEY", b'V0h0a1F4d1Z5T3p5Um92TDB3SFB5TG9rV3B5d1N2YlE=')
if isinstance(FIXED_SECRET_KEY, str):
    FIXED_SECRET_KEY = FIXED_SECRET_KEY.encode()

try:
    cipher = Fernet(FIXED_SECRET_KEY)
except Exception:
    fallback_key = Fernet.generate_key()
    cipher = Fernet(fallback_key)

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
            try:
                await self.active_connections[recipient].send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- BACKEND APIS ---
@app.post("/api/register")
async def register_user(data: dict):
    if not supabase:
        return {"status": "error", "detail": "خطأ في اتصال قاعدة البيانات"}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return {"status": "error", "detail": "الاسم وكلمة السر مطلوبان"}
    try:
        res = supabase.table("users").select("username").eq("username", username).execute()
        if res.data and len(res.data) > 0:
            return {"status": "error", "detail": "اسم المستخدم موجود سابقاً"}
        all_u = supabase.table("users").select("username").execute()
        assigned_role = "admin" if not all_u.data or len(all_u.data) == 0 else "user"
        rec_key = generate_recovery_key()
        u_id = generate_user_id()
        payload = {
            "username": username,
            "display_name": username, 
            "password": hash_data(password),
            "recovery_key": hash_data(rec_key),
            "role": assigned_role,
            "user_id": u_id,
            "avatar": "",
            "status_text": "Available",
            "bio": "مرحباً! أنا أستخدم Cyber Messenger.",
            "friends": [],
            "friend_requests": [],
            "blocked": []
        }
        supabase.table("users").insert(payload).execute()
        return {"status": "success", "user_id": u_id, "recovery_key": rec_key}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/login")
async def login_user(data: dict):
    if not supabase:
        return {"status": "error", "detail": "خطأ في اتصال قاعدة البيانات"}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return {"status": "error", "detail": "الرجاء إدخال اسم المستخدم وكلمة السر"}
    try:
        res = supabase.table("users").select("*").eq("username", username).execute()
        if not res.data or len(res.data) == 0:
            return {"status": "error", "detail": "اسم المستخدم غير موجود"}
        
        user_record = res.data[0]
        if user_record.get("password") != hash_data(password):
            return {"status": "error", "detail": "كلمة المرور غير صحيحة"}
            
        return {"status": "success", "user": user_record}
    except Exception as e:
        return {"status": "error", "detail": f"خطأ سيرفر: {str(e)}"}

@app.get("/api/get_user/{username}")
async def get_user_data(username: str):
    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data or len(res.data) == 0:
        return {"status": "error", "detail": "غير موجود"}
    return {"status": "success", "user": res.data[0]}

@app.get("/api/get_all_users")
async def get_all_users_api():
    res = supabase.table("users").select("username, display_name, user_id, bio, status_text, avatar, friend_requests, friends, blocked").execute()
    return {"status": "success", "users": res.data or []}

@app.get("/api/get_messages/{u1}/{u2}")
async def get_messages_api(u1: str, u2: str):
    try:
        res1 = supabase.table("messages").select("*").eq("sender", u1).eq("recipient", u2).execute().data or []
        res2 = supabase.table("messages").select("*").eq("sender", u2).eq("recipient", u1).execute().data or []
        all_msgs = res1 + res2
        all_msgs.sort(key=lambda x: x.get("created_at", ""))
        
        decrypted_msgs = []
        for m in all_msgs:
            try:
                raw_content = m.get('content', '')
                if raw_content and raw_content.startswith("gAAAAAB"):
                    m['content'] = cipher.decrypt(raw_content.encode()).decode()
                else:
                    m['content'] = raw_content
            except Exception:
                pass
            decrypted_msgs.append(m)
        return {"status": "success", "messages": decrypted_msgs}
    except Exception as e:
        return {"status": "error", "messages": [], "detail": str(e)}

@app.post("/api/send_message_http")
async def send_message_http(data: dict):
    sender = data.get("sender")
    recipient = data.get("recipient")
    content = data.get("message", "").strip()
    file_data = data.get("file")
    is_burn = data.get("is_burn", False)

    if not sender or not recipient or (not content and not file_data):
        return {"status": "error", "detail": "بيانات ناقصة"}

    final_payload = content
    if file_data:
        final_payload += f"\n[FILE:{file_data['name']}:{file_data['type']}]{file_data['base64']}"

    if is_burn:
        final_payload = f"[BURN]{final_payload}"

    enc_content = cipher.encrypt(final_payload.encode()).decode()
    msg_id = secrets.token_hex(8)

    db_payload = {
        "id": msg_id,
        "sender": sender,
        "recipient": recipient,
        "content": enc_content
    }
    
    try:
        supabase.table("messages").insert(db_payload).execute()
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    msg_out = {
        "id": msg_id,
        "sender": sender,
        "recipient": recipient,
        "content": final_payload,
        "time": "الآن"
    }
    
    await manager.send_to_user(recipient, msg_out)
    await manager.send_to_user(sender, msg_out)

    return {"status": "success", "message": msg_out}

@app.post("/api/burn_message")
async def burn_message(data: dict):
    msg_id = data.get("id")
    try:
        supabase.table("messages").delete().eq("id", msg_id).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/update_user")
async def update_user(data: dict):
    username = data.get("username")
    updates = data.get("updates", {})
    if "friends" in updates and isinstance(updates["friends"], list):
        updates["friends"] = list(set(updates["friends"]))
    if "friend_requests" in updates and isinstance(updates["friend_requests"], list):
        updates["friend_requests"] = list(set(updates["friend_requests"]))
    if "blocked" in updates and isinstance(updates["blocked"], list):
        updates["blocked"] = list(set(updates["blocked"]))

    try:
        supabase.table("users").update(updates).eq("username", username).execute()
        res = supabase.table("users").select("*").eq("username", username).execute()
        return {"status": "success", "user": res.data[0]}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# --- UI HTML INTERFACE ---
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
        .auth-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); padding: 35px; border-radius: 20px; width: 440px; }
        .auth-card h1 { color: #3b82f6; font-size: 2.2em; font-weight: 800; text-align: center; }
        .auth-card p { color: #94a3b8; text-align: center; margin-bottom: 20px; }
        
        .auth-tabs { display: flex; gap: 8px; margin-bottom: 20px; background: #090d16; padding: 5px; border-radius: 12px; }
        .tab-btn { flex: 1; padding: 8px; background: transparent; border: none; color: #94a3b8; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .tab-btn.active { background: #2563eb; color: #fff; }

        .auth-form { display: none; }
        .auth-form.active { display: block; }
        .auth-form input { width: 100%; padding: 12px; margin-bottom: 12px; background: #090d16; border: 1px solid #334155; border-radius: 10px; color: #fff; outline: none; }
        .auth-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; transition: 0.2s; }
        .auth-btn:hover { opacity: 0.9; transform: scale(0.98); }

        .sidebar { width: 300px; background: #111827; border-right: 1px solid rgba(255, 255, 255, 0.08); padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        .sidebar-profile { text-align: center; margin-bottom: 10px; }
        .avatar-circle { width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #1e1b4b); color: #f8fafc; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #3b82f6; font-size: 30px; margin: 0 auto 10px auto; overflow: hidden; }
        .avatar-circle img { width: 100%; height: 100%; object-fit: cover; }
        
        .nav-btn { background: rgba(30, 41, 59, 0.4); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 12px 16px; text-align: left; font-size: 0.95em; font-weight: 600; width: 100%; cursor: pointer; margin-bottom: 6px; }
        .nav-btn:hover, .nav-btn.active { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; }

        .main-container { flex: 1; display: flex; flex-direction: column; background: #090d16; }
        .page-content { flex: 1; display: none; padding: 24px; overflow-y: auto; }
        .page-content.active { display: flex; flex-direction: column; }

        .chat-container-layout { flex: 1; display: flex; gap: 15px; height: calc(100vh - 120px); }
        .friends-sidebar { width: 260px; background: #111827; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 15px; overflow-y: auto; }
        .friend-item { padding: 12px; background: #090d16; border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 10px;}
        .friend-item:hover, .friend-item.active { background: #2563eb; border-color: #3b82f6; }
        .small-avatar { width: 35px; height: 35px; border-radius: 50%; background: #1e293b; display: flex; align-items: center; justify-content: center; overflow: hidden; font-size: 14px; }
        .small-avatar img { width: 100%; height: 100%; object-fit: cover; }

        .chat-main-area { flex: 1; display: flex; flex-direction: column; background: #111827; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 16px; }
        .chat-header-bar { padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
        .chat-message-container { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 12px; background: #0b0f19; border-radius: 14px; }
        
        .msg-wrapper { display: flex; width: 100%; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }
        .insta-bubble { max-width: 68%; padding: 10px 14px; border-radius: 16px; font-size: 0.95em; word-break: break-word; }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #ffffff; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; }
        .burn-bubble { background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%) !important; border: 1px dashed #fca5a5; cursor: pointer; }

        .input-bar { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
        .input-bar textarea { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 10px 14px; color: #fff; outline: none; height: 45px; resize: none; font-size: 0.95em; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 16px; height: 45px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .attach-btn, .mic-btn, .burn-toggle-btn { background: #1e293b; color: #94a3b8; border: 1px solid rgba(255,255,255,0.1); width: 45px; height: 45px; border-radius: 12px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1.2em; transition: 0.2s; }
        .burn-toggle-btn.active { background: #dc2626; color: #fff; border-color: #f87171; }
        .mic-btn.recording { background: #ef4444; color: #fff; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

        .st-tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 10px; }
        .st-tab-btn { background: rgba(30, 41, 59, 0.5); color: #94a3b8; border: none; padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .st-tab-btn.active { background: #2563eb; color: #fff; }
        .st-tab-content { display: none; }
        .st-tab-content.active { display: block; }

        .user-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px 16px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
        .card-box { background: #111827; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 22px; text-align: center; flex: 1; }
        
        .modal-overlay-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); z-index: 10000; align-items: center; justify-content: center; }
        .modal-overlay-bg.active { display: flex; }
        .profile-modal { background: #111827; border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; width: 340px; padding: 30px; text-align: center; position: relative; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
        .profile-modal .close-btn { position: absolute; top: 15px; right: 20px; background: transparent; border: none; color: #94a3b8; font-size: 1.5em; cursor: pointer; }
        .modal-avatar-lg { width: 110px; height: 110px; border-radius: 50%; border: 3px solid #3b82f6; margin: 0 auto 15px auto; overflow: hidden; background: #1e293b; display: flex; align-items: center; justify-content: center; font-size: 45px; }
        .modal-avatar-lg img { width: 100%; height: 100%; object-fit: cover; }
    </style>
</head>
<body>

    <!-- Auth Modal -->
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
            <div id="auth-err-msg" style="color:#ef4444; font-size:0.85em; text-align:center; margin-top:10px; font-weight:bold;"></div>
        </div>
    </div>

    <!-- User Profile Modal Card -->
    <div class="modal-overlay-bg" id="user-profile-modal">
        <div class="profile-modal">
            <button class="close-btn" onclick="document.getElementById('user-profile-modal').classList.remove('active')">✖</button>
            <div id="modal-avatar" class="modal-avatar-lg">👤</div>
            <h2 id="modal-display-name" style="color:#f8fafc; margin-bottom:4px; font-weight:800;">Name</h2>
            <p id="modal-username" style="color:#60a5fa; font-size:0.9em; margin-bottom:20px; font-family:monospace;">@username</p>
            <div style="background:#090d16; padding:15px; border-radius:12px; text-align:right; border:1px solid rgba(255,255,255,0.05);">
                <p style="color:#94a3b8; font-size:0.85em; margin-bottom:6px;"><strong>📝 النبذة التعريفيّة (Bio):</strong></p>
                <p id="modal-bio" style="color:#e2e8f0; font-size:0.95em; line-height:1.5;">لا توجد نبذة حتى الآن.</p>
            </div>
        </div>
    </div>

    <div class="sidebar">
        <div class="sidebar-profile">
            <div class="avatar-circle" id="user-avatar-disp">👤</div>
            <h3 id="user-name-disp" style="color:#f8fafc; font-weight:700;">User</h3>
            <p id="user-username-disp" style="color: #94a3b8; font-size: 0.82em; margin-bottom: 6px;">@username</p>
            <p id="user-status-disp" style="color: #60a5fa; font-size: 0.82em; margin-bottom: 6px;">"Available"</p>
        </div>
        <hr style="border:0.5px solid rgba(255,255,255,0.08); margin: 10px 0;">
        <button class="nav-btn active" onclick="showPage('dashboard', this)">🏠 Dashboard</button>
        <button class="nav-btn" onclick="showPage('messages', this)">💬 Messages</button>
        <button class="nav-btn" onclick="showPage('friends', this)">👥 Friends</button>
        <button class="nav-btn" onclick="showPage('profile', this)">👤 Profile Settings</button>
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
            <div class="chat-container-layout">
                <div class="friends-sidebar">
                    <h4 style="margin-bottom:12px; color:#60a5fa;">💬 قائمة الأصدقاء</h4>
                    <div id="chat-friends-list"></div>
                </div>
                <div class="chat-main-area">
                    <div class="chat-header-bar">
                        <div><strong id="target-disp-name">اختر صديقاً من القائمة على اليسار لبدء المحادثة</strong></div>
                        <span style="background:#059669; color:#fff; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;">🔒 مشفر</span>
                    </div>
                    <div class="chat-message-container" id="chat-box"></div>
                    <div id="file-preview-name" style="font-size:0.8em; color:#60a5fa; margin-top:4px; display:none;"></div>
                    <div class="input-bar">
                        <button class="burn-toggle-btn" id="burn-btn" title="رسالة ذاتية الاحتراق (تختفي بعد القراءة)" onclick="toggleBurnMode()">🔥</button>
                        <button class="mic-btn" id="mic-btn" title="تسجيل صوتي" onclick="toggleVoiceRecording()">🎤</button>
                        <label class="attach-btn" for="file-input" title="إرفاق ملف">📎</label>
                        <input type="file" id="file-input" style="display:none;" onchange="handleFileSelect(this)">
                        <textarea id="msg-input" placeholder="اكتب رسالة..." onkeydown="handleEnterKey(event)"></textarea>
                        <button class="send-btn" onclick="sendMsg()">إرسال 🚀</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="page-content" id="page-friends">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h3>👥 Friend Management</h3>
                <button class="auth-btn" style="width:auto; padding:6px 14px;" onclick="refreshUserData()">🔄 تحديث البيانات</button>
            </div>
            <div class="st-tabs">
                <button class="st-tab-btn active" onclick="switchStTab('search', this)">🔍 Search & Add</button>
                <button class="st-tab-btn" onclick="switchStTab('myfriends', this)">👥 My Friends</button>
                <button class="st-tab-btn" onclick="switchStTab('requests', this)">📩 Requests</button>
            </div>
            <div class="st-tab-content active" id="tab-search">
                <input type="text" id="s_query_key" placeholder="ابحث باسم المستخدم أو الـ ID..." style="width:100%; padding:10px; background:#111827; border:1px solid rgba(255,255,255,0.1); border-radius:8px; color:#fff; outline:none; margin-bottom:10px;" oninput="searchUsersLive()">
                <div id="search-results-list"></div>
            </div>
            <div class="st-tab-content" id="tab-myfriends"><div id="my-friends-tab-list"></div></div>
            <div class="st-tab-content" id="tab-requests"><div id="requests-tab-list"></div></div>
        </div>

        <div class="page-content" id="page-profile">
            <h3>👤 Profile Settings</h3>
            <div style="background:#111827; padding:30px; border-radius:16px; margin-top:15px; max-width: 500px;">
                <div style="text-align:center; margin-bottom: 25px;">
                    <label for="avatar-upload" style="cursor:pointer; display:inline-block;">
                        <div class="avatar-circle" id="prof-avatar-preview" style="width:100px; height:100px; font-size:40px; margin:0 auto; border:3px dashed #3b82f6;">👤</div>
                        <p style="color:#60a5fa; font-size:0.85em; margin-top:10px; font-weight:bold;">تغيير الصورة الشخصية 📷</p>
                    </label>
                    <input type="file" id="avatar-upload" style="display:none;" accept="image/*" onchange="handleAvatarUpload(this)">
                </div>

                <label style="font-size:0.85em; color:#94a3b8; font-weight:bold;">الاسم المعروض (Display Name)</label>
                <input type="text" id="prof-display-name" placeholder="اسمك الذي سيظهر للآخرين" style="width:100%; padding:12px; background:#090d16; border:1px solid #334155; border-radius:10px; color:#fff; margin-bottom:15px; margin-top:5px;">
                
                <label style="font-size:0.85em; color:#94a3b8; font-weight:bold;">الحالة (Status)</label>
                <input type="text" id="prof-status" placeholder="متوفر، مشغول..." style="width:100%; padding:12px; background:#090d16; border:1px solid #334155; border-radius:10px; color:#fff; margin-bottom:15px; margin-top:5px;">
                
                <label style="font-size:0.85em; color:#94a3b8; font-weight:bold;">النبذة التعريفيّة (Bio)</label>
                <textarea id="prof-bio" placeholder="اكتب شيئاً عن نفسك..." style="width:100%; padding:12px; background:#090d16; border:1px solid #334155; border-radius:10px; color:#fff; margin-bottom:20px; margin-top:5px; height: 80px; resize:none;"></textarea>
                
                <button class="auth-btn" style="padding:14px; font-size:1.05em;" onclick="saveProfile()">حفظ التعديلات 💾</button>
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
        let selectedChatFriend = null;
        let allUsersCache = [];
        let attachedFileData = null;
        let pendingAvatarBase64 = null; 
        let isBurnMode = false;
        let mediaRecorder = null;
        let audioChunks = [];

        function switchAuthTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            document.getElementById('auth-err-msg').innerText = "";
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
            const errBox = document.getElementById('auth-err-msg');
            
            if(!u || !p) {
                errBox.innerText = "الرجاء إدخال اسم المستخدم وكلمة المرور";
                return;
            }

            errBox.innerText = "جاري تسجيل الدخول...";

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                if(data.status === "success") {
                    errBox.innerText = "";
                    initUserSession(data.user);
                } else {
                    errBox.innerText = data.detail || "خطأ في معلومات الدخول";
                }
            } catch(err) {
                errBox.innerText = "فشل الاتصال بالخادم، تأكد من الإنترنت أو أعِد المحاولة";
            }
        }

        async function apiRegister() {
            const u = document.getElementById('r_u').value.trim();
            const p = document.getElementById('r_p').value.trim();
            const errBox = document.getElementById('auth-err-msg');
            
            if(!u || !p) {
                errBox.innerText = "الرجاء تعبئة الحقول المطلوبة";
                return;
            }

            errBox.innerText = "جاري إنشاء الحساب...";

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                if(data.status === "success") {
                    errBox.innerText = "";
                    alert(`تم التسجيل بنجاح! ID الخاص بك: ${data.user_id}`);
                    switchAuthTab('login');
                } else {
                    errBox.innerText = data.detail || "خطأ في التسجيل";
                }
            } catch(err) {
                errBox.innerText = "فشل الاتصال بالخادم";
            }
        }

        function connectWebSocket() {
            if(!userData) return;
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${userData.username}`);
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (selectedChatFriend && ((data.sender === selectedChatFriend && data.recipient === userData.username) || (data.sender === userData.username && data.recipient === selectedChatFriend))) {
                        appendParsedBubble(data.id, data.sender, data.content, data.time);
                    }
                } catch(err) {}
            };
            ws.onclose = function() {
                setTimeout(connectWebSocket, 2000);
            };
        }

        function initUserSession(user) {
            userData = user;
            if(userData.friends) {
                userData.friends = [...new Set(userData.friends)];
            }
            updateUIProfile();
            document.getElementById('auth-modal').style.display = 'none';
            connectWebSocket();
            refreshUserData();
        }

        async function refreshUserData() {
            if(!userData) return;
            try {
                const res = await fetch(`/api/get_user/${userData.username}`);
                const data = await res.json();
                if(res.ok && data.user) {
                    userData = data.user;
                    if(userData.friends) userData.friends = [...new Set(userData.friends)];
                    if(userData.friend_requests) userData.friend_requests = [...new Set(userData.friend_requests)];
                    if(userData.blocked) userData.blocked = [...new Set(userData.blocked)];

                    updateUIProfile();
                    renderChatFriendsSidebar();
                }
                const resAll = await fetch('/api/get_all_users');
                const dataAll = await resAll.json();
                if(resAll.ok && dataAll.users) {
                    allUsersCache = dataAll.users;
                    renderFriendsTabs();
                    renderBlocklist();
                }
            } catch(e) {}
        }

        function getUserDetails(username) {
            const u = allUsersCache.find(x => x.username === username);
            if(u) {
                return {
                    name: u.display_name || u.username,
                    avatarHtml: u.avatar ? `<img src="${u.avatar}">` : '👤',
                    bio: u.bio || 'لا توجد نبذة.',
                    id: u.user_id
                };
            }
            return { name: username, avatarHtml: '👤', bio: '', id: '' };
        }

        function updateUIProfile() {
            const dispName = userData.display_name || userData.username;
            document.getElementById('user-name-disp').innerText = dispName;
            document.getElementById('user-username-disp').innerText = `@${userData.username}`;
            document.getElementById('user-status-disp').innerText = `"${userData.status_text || 'Available'}"`;
            
            document.getElementById('prof-display-name').value = dispName;
            document.getElementById('prof-status').value = userData.status_text || '';
            document.getElementById('prof-bio').value = userData.bio || '';

            const avatarHtml = userData.avatar ? `<img src="${userData.avatar}">` : '👤';
            document.getElementById('user-avatar-disp').innerHTML = avatarHtml;
            document.getElementById('prof-avatar-preview').innerHTML = avatarHtml;

            const flist = userData.friends ? [...new Set(userData.friends)] : [];
            const rlist = userData.friend_requests ? [...new Set(userData.friend_requests)] : [];
            document.getElementById('dash-friends-count').innerText = flist.length;
            document.getElementById('dash-reqs-count').innerText = rlist.length;
        }

        function handleAvatarUpload(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                pendingAvatarBase64 = e.target.result;
                document.getElementById('prof-avatar-preview').innerHTML = `<img src="${pendingAvatarBase64}">`;
            };
            reader.readAsDataURL(file);
        }

        async function saveProfile() {
            const display_name = document.getElementById('prof-display-name').value.trim() || userData.username;
            const status_text = document.getElementById('prof-status').value;
            const bio = document.getElementById('prof-bio').value;
            
            let updates = { display_name, status_text, bio };
            if(pendingAvatarBase64) {
                updates.avatar = pendingAvatarBase64;
            }

            const res = await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: updates})
            });
            if(res.ok) {
                alert("تم تحديث البروفايل بنجاح! ✅");
                pendingAvatarBase64 = null;
                refreshUserData();
            }
        }

        function showProfileCard(targetUsername) {
            const u = getUserDetails(targetUsername);
            document.getElementById('modal-avatar').innerHTML = u.avatarHtml;
            document.getElementById('modal-display-name').innerText = u.name;
            document.getElementById('modal-username').innerText = `@${targetUsername} (${u.id})`;
            document.getElementById('modal-bio').innerText = u.bio;
            document.getElementById('user-profile-modal').classList.add('active');
        }

        function renderChatFriendsSidebar() {
            const box = document.getElementById('chat-friends-list');
            box.innerHTML = "";
            const flist = userData.friends ? [...new Set(userData.friends)] : [];
            if(flist.length === 0) {
                box.innerHTML = "<p style='color:#94a3b8; font-size:0.85em;'>لا يوجد أصدقاء بعد.</p>";
            } else {
                flist.forEach(f => {
                    const activeCls = (selectedChatFriend === f) ? "active" : "";
                    const u = getUserDetails(f);
                    box.innerHTML += `
                    <div class="friend-item ${activeCls}" onclick="openChatWith('${f}', this)">
                        <div class="small-avatar">${u.avatarHtml}</div>
                        <strong>${u.name}</strong>
                    </div>`;
                });
            }
        }

        async function openChatWith(friendName, el) {
            selectedChatFriend = friendName;
            document.querySelectorAll('.friend-item').forEach(i => i.classList.remove('active'));
            if(el) el.classList.add('active');

            const u = getUserDetails(friendName);
            document.getElementById('target-disp-name').innerHTML = `محادثة مع: ${u.name} <button class="auth-btn" style="padding:2px 8px; width:auto; font-size:0.7em; margin-right:10px; background:#1e293b;" onclick="showProfileCard('${friendName}')">👁️ بروفايل</button>`;
            
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML = "<p style='color:#94a3b8;'>جاري تحميل السجل...</p>";

            try {
                const res = await fetch(`/api/get_messages/${userData.username}/${friendName}`);
                const data = await res.json();
                chatBox.innerHTML = "";

                if(res.ok && data.messages && data.messages.length > 0) {
                    const uniqueMessages = Array.from(new Map(data.messages.map(m => [m.id, m])).values());
                    
                    uniqueMessages.forEach(m => {
                        appendParsedBubble(m.id, m.sender, m.content, m.created_at ? m.created_at.substring(11, 16) : 'الآن');
                    });
                } else {
                    chatBox.innerHTML = "<p style='color:#94a3b8;'>لا توجد رسائل سابقة. ابدأ المحادثة الآن!</p>";
                }
            } catch(e) {
                chatBox.innerHTML = "<p style='color:#ef4444;'>خطأ في الاتصال.</p>";
            }
        }

        function handleEnterKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMsg();
            }
        }

        function toggleBurnMode() {
            isBurnMode = !isBurnMode;
            const btn = document.getElementById('burn-btn');
            if(isBurnMode) {
                btn.classList.add('active');
                btn.title = "وضع الاحتراق مفعّل (الرسالة ستختفي بمجرد رؤيتها)";
            } else {
                btn.classList.remove('active');
                btn.title = "رسالة ذاتية الاحتراق";
            }
        }

        async function toggleVoiceRecording() {
            const micBtn = document.getElementById('mic-btn');
            if (!mediaRecorder || mediaRecorder.state === "inactive") {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    audioChunks = [];
                    mediaRecorder = new MediaRecorder(stream);
                    
                    mediaRecorder.ondataavailable = event => {
                        audioChunks.push(event.data);
                    };

                    mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                        const reader = new FileReader();
                        reader.onload = async function(e) {
                            attachedFileData = {
                                name: "voice_note.webm",
                                type: "audio/webm",
                                base64: e.target.result
                            };
                            await sendMsg();
                        };
                        reader.readAsDataURL(audioBlob);
                    };

                    mediaRecorder.start();
                    micBtn.classList.add('recording');
                    micBtn.title = "جارٍ التسجيل... انقر للإيقاف والإرسال";
                } catch (err) {
                    alert("لا يمكن الوصول إلى الميكروفون!");
                }
            } else {
                mediaRecorder.stop();
                micBtn.classList.remove('recording');
                micBtn.title = "تسجيل صوتي";
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
                prev.innerText = `📁 تم إرفاق: ${file.name}`;
                prev.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }

        async function sendMsg() {
            const input = document.getElementById("msg-input");
            const msg = input.value.trim();

            if(!selectedChatFriend) return alert("اختر صديقاً من القائمة أولاً!");
            if(!msg && !attachedFileData) return;

            const payload = {
                sender: userData.username,
                recipient: selectedChatFriend,
                message: msg,
                file: attachedFileData,
                is_burn: isBurnMode
            };

            let localContent = msg;
            let tempFile = attachedFileData;
            let tempBurn = isBurnMode;

            if(tempFile) {
                localContent += `\\n[FILE:${tempFile.name}:${tempFile.type}]${tempFile.base64}`;
            }
            if(tempBurn) {
                localContent = `[BURN]` + localContent;
            }

            input.value = "";
            attachedFileData = null;
            isBurnMode = false;
            document.getElementById('burn-btn').classList.remove('active');
            document.getElementById('file-preview-name').style.display = 'none';
            document.getElementById('file-input').value = "";

            try {
                const res = await fetch('/api/send_message_http', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if(data.status === "success") {
                    appendParsedBubble(data.message.id, data.message.sender, data.message.content, 'الآن');
                }
            } catch(e) {}
        }

        function appendParsedBubble(msgId, sender, rawContent, time) {
            let textPart = rawContent || '';
            let fileHtml = '';
            let isBurn = false;

            if (textPart.startsWith("[BURN]")) {
                isBurn = true;
                textPart = textPart.replace("[BURN]", "");
            }

            if (textPart.includes("[FILE:")) {
                const parts = textPart.split("[FILE:");
                textPart = parts[0];
                const fileMeta = parts[1].split("]");
                const fileNameType = fileMeta[0].split(":");
                const fileBase64 = fileMeta[1];
                const fileType = fileNameType[1] || "";
                const fileName = fileNameType[0] || "file";

                if (fileType.startsWith("image/")) {
                    fileHtml = `<br><img src="${fileBase64}" style="max-width:200px; border-radius:8px; margin-top:6px; display:block;">`;
                } else if (fileType.startsWith("audio/")) {
                    fileHtml = `<br><audio controls src="${fileBase64}" style="width:220px; margin-top:6px;"></audio>`;
                } else {
                    fileHtml = `<br><a href="${fileBase64}" download="${fileName}" style="color:#60a5fa; font-size:0.85em; display:inline-block; margin-top:6px;">📄 تنزيل ${fileName}</a>`;
                }
            }

            const isMine = (sender === userData.username);
            const chatBox = document.getElementById("chat-box");
            if (!chatBox) return;

            const wrapper = document.createElement("div");
            wrapper.className = "msg-wrapper " + (isMine ? "sent" : "received");
            let bubbleClass = "insta-bubble";

            if (isBurn) {
                bubbleClass += " burn-bubble";
                if (!isMine) {
                    wrapper.innerHTML = `<div class="${bubbleClass}" onclick="burnAndReadMessage(this, '${msgId}', \`${textPart}\`, \`${fileHtml}\`)">🔥 رسالة ذاتية الاحتراق (انقر للفتح)</div>`;
                    chatBox.appendChild(wrapper);
                    chatBox.scrollTop = chatBox.scrollHeight;
                    return;
                } else {
                    textPart = `🔥 [رسالة ذاتية الاحتراق مرسلة] ` + textPart;
                }
            }

            wrapper.innerHTML = `<div class="${bubbleClass}">${textPart}${fileHtml}<span style="font-size:0.65em; display:block; opacity:0.7; text-align:right; margin-top:4px;">${time || 'الآن'}</span></div>`;
            chatBox.appendChild(wrapper);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function burnAndReadMessage(element, msgId, textPart, fileHtml) {
            element.innerHTML = `${textPart}${fileHtml}<span style="font-size:0.65em; display:block; opacity:0.7; text-align:right; margin-top:4px; color:#fca5a5;">تم حرق الرسالة 💥</span>`;
            element.style.cursor = "default";
            element.onclick = null;

            await fetch('/api/burn_message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: msgId})
            });
        }

        function switchStTab(tabId, btnEl) {
            document.querySelectorAll('.st-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.st-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            btnEl.classList.add('active');
        }

        function searchUsersLive() {
            const q = document.getElementById('s_query_key').value.trim().toLowerCase();
            const box = document.getElementById('search-results-list');
            box.innerHTML = "";
            if(!q) return;

            allUsersCache.forEach(u => {
                if(u.username !== userData.username && (u.username.toLowerCase().includes(q) || (u.display_name && u.display_name.toLowerCase().includes(q)) || (u.user_id && u.user_id.toLowerCase().includes(q)))) {
                    const isFriend = (userData.friends || []).includes(u.username);
                    const isPending = (userData.friend_requests || []).includes(u.username);
                    const ud = getUserDetails(u.username);

                    let actionBtn = `<button class="auth-btn" style="width:auto; padding:6px 12px;" onclick="sendReq('${u.username}')">➕ إضافة</button>`;
                    if(isFriend) actionBtn = `<span style="color:#10b981; font-weight:bold;">صديق ✅</span>`;
                    else if(isPending) actionBtn = `<span style="color:#f59e0b; font-weight:bold;">معلق ⏳</span>`;

                    box.innerHTML += `
                    <div class="user-card">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div class="small-avatar" style="width:45px; height:45px;">${ud.avatarHtml}</div>
                            <div>
                                <strong style="color:#f8fafc;">${ud.name}</strong>
                                <span style="color:#60a5fa; font-size:0.88em; margin-left:6px;">(@${u.username})</span>
                            </div>
                        </div>
                        <div style="display:flex; gap:5px;">
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#1e293b;" onclick="showProfileCard('${u.username}')">👁️ بروفايل</button>
                            ${actionBtn}
                        </div>
                    </div>`;
                }
            });
        }

        async function sendReq(uname) {
            const uObj = allUsersCache.find(x => x.username === uname);
            let reqs = uObj.friend_requests || [];
            if(!reqs.includes(userData.username)) reqs.push(userData.username);
            reqs = [...new Set(reqs)];

            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: uname, updates: {friend_requests: reqs}})
            });
            alert(`تم إرسال الطلب إلى ${uname}!`);
            refreshUserData();
        }

        function renderFriendsTabs() {
            const myfBox = document.getElementById('my-friends-tab-list');
            myfBox.innerHTML = "";
            const flist = userData.friends ? [...new Set(userData.friends)] : [];
            if(flist.length === 0) myfBox.innerHTML = "<p style='color:#94a3b8;'>لا يوجد أصدقاء حالياً.</p>";
            else {
                flist.forEach(f => {
                    const ud = getUserDetails(f);
                    myfBox.innerHTML += `
                    <div class="user-card">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div class="small-avatar">${ud.avatarHtml}</div>
                            <strong style="color:#f8fafc;">${ud.name}</strong>
                        </div>
                        <div style="display:flex; gap:6px;">
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#1e293b;" title="بروفايل" onclick="showProfileCard('${f}')">👁️</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px;" title="محادثة" onclick="startChatFromFriends('${f}')">💬</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" title="حذف" onclick="unfriend('${f}')">🗑️</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" title="حظر" onclick="blockUser('${f}')">🚫</button>
                        </div>
                    </div>`;
                });
            }

            const reqBox = document.getElementById('requests-tab-list');
            reqBox.innerHTML = "";
            const reqs = userData.friend_requests ? [...new Set(userData.friend_requests)] : [];
            if(reqs.length === 0) reqBox.innerHTML = "<p style='color:#94a3b8;'>لا توجد طلبات معلقة.</p>";
            else {
                reqs.forEach(r => {
                    const ud = getUserDetails(r);
                    reqBox.innerHTML += `
                    <div class="user-card">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div class="small-avatar">${ud.avatarHtml}</div>
                            <strong style="color:#f8fafc;">${ud.name}</strong>
                        </div>
                        <div style="display:flex; gap:6px;">
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#059669;" onclick="acceptReq('${r}')">✅ قبول</button>
                            <button class="auth-btn" style="width:auto; padding:6px 12px; background:#ef4444;" onclick="declineReq('${r}')">❌ رفض</button>
                        </div>
                    </div>`;
                });
            }
        }

        function startChatFromFriends(fname) {
            showPage('messages', document.querySelectorAll('.nav-btn')[1]);
            openChatWith(fname, null);
        }

        async function acceptReq(rUser) {
            let myF = userData.friends ? [...new Set(userData.friends)] : [];
            let myR = userData.friend_requests ? [...new Set(userData.friend_requests)] : [];
            myF.push(rUser);
            myF = [...new Set(myF)];
            myR = myR.filter(x => x !== rUser);

            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {friends: myF, friend_requests: myR}})
            });

            const rObj = allUsersCache.find(x => x.username === rUser);
            let rF = rObj && rObj.friends ? [...new Set(rObj.friends)] : [];
            rF.push(userData.username);
            rF = [...new Set(rF)];

            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: rUser, updates: {friends: rF}})
            });

            refreshUserData();
        }

        async function declineReq(rUser) {
            let myR = userData.friend_requests ? userData.friend_requests.filter(x => x !== rUser) : [];
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {friend_requests: myR}})
            });
            refreshUserData();
        }

        async function unfriend(fUser) {
            let myF = userData.friends ? userData.friends.filter(x => x !== fUser) : [];
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {friends: myF}})
            });
            refreshUserData();
        }

        async function blockUser(fUser) {
            let myB = userData.blocked ? [...new Set(userData.blocked)] : [];
            let myF = userData.friends ? userData.friends.filter(x => x !== fUser) : [];
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
            if(!bBox) return;
            bBox.innerHTML = "";
            const blist = userData.blocked ? [...new Set(userData.blocked)] : [];
            if(blist.length === 0) bBox.innerHTML = "<p style='color:#94a3b8;'>لا يوجد مستخدمين محظورين.</p>";
            else {
                blist.forEach(b => {
                    const ud = getUserDetails(b);
                    bBox.innerHTML += `
                    <div class="user-card">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div class="small-avatar">${ud.avatarHtml}</div>
                            <strong style="color:#f8fafc;">${ud.name}</strong>
                        </div>
                        <button class="auth-btn" style="width:auto; padding:6px 12px; background:#059669;" onclick="unblock('${b}')">✅ فك الحظر</button>
                    </div>`;
                });
            }
        }

        async function unblock(bUser) {
            let myB = userData.blocked ? userData.blocked.filter(x => x !== bUser) : [];
            await fetch('/api/update_user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: userData.username, updates: {blocked: myB}})
            });
            refreshUserData();
        }

        function showPage(pageId, btnEl) {
            document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
            if(btnEl) btnEl.classList.add('active');
            if(pageId === 'friends' || pageId === 'blocklist' || pageId === 'messages') refreshUserData();
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
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(username)
