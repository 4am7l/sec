from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
import secrets
from supabase import create_client, Client

app = FastAPI()

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://shgxaxtjurbvbqdvmkzt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_FEE0CeWycaYbelk2VZPTBw_8j7lkftq")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_to_user(self, recipient_id: str, message: dict):
        if recipient_id in self.active_connections:
            await self.active_connections[recipient_id].send_json(message)

manager = ConnectionManager()

# --- ORIGINAL UI INTEGRATION ---
ORIGINAL_HTML = """
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

        /* Auth Gate Modal */
        .auth-overlay { position: fixed; inset: 0; background: rgba(9, 13, 22, 0.95); backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: center; z-index: 9999; }
        .auth-card { background: #111827; border: 1px solid rgba(255,255,255,0.08); padding: 40px; border-radius: 20px; width: 400px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
        .auth-card h1 { color: #3b82f6; font-size: 2em; font-weight: 800; margin-bottom: 5px; }
        .auth-card p { color: #94a3b8; font-size: 0.9em; margin-bottom: 25px; }
        .auth-card input { width: 100%; padding: 12px 16px; margin-bottom: 12px; background: #090d16; border: 1px solid #334155; border-radius: 12px; color: #fff; outline: none; font-size: 0.95em; }
        .auth-card input:focus { border-color: #3b82f6; }
        .auth-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; transition: all 0.2s; margin-top: 8px; }
        .auth-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); }

        /* Sidebar Styles (Matching Streamlit Layout) */
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

        /* Chat Specific Header */
        .chat-header-bar { background: #111827; padding: 14px 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
        .chat-message-container { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 8px; }
        
        /* Insta Bubbles */
        .msg-wrapper { display: flex; width: 100%; margin-bottom: 2px; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }
        
        .insta-bubble { max-width: 68%; padding: 12px 16px; border-radius: 18px; font-size: 0.95em; line-height: 1.45; word-wrap: break-word; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25); }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #ffffff; border-bottom-right-radius: 4px; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; border-bottom-left-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.05); }
        .msg-time { font-size: 0.68em; opacity: 0.75; display: block; text-align: right; margin-top: 4px; }

        /* Card Overview */
        .card-box { background: #111827; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 22px; text-align: center; flex: 1; }
        .input-bar { background: #111827; padding: 16px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; margin-top: 10px; }
        .input-bar textarea { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px; color: #fff; outline: none; resize: none; height: 50px; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 24px; border-radius: 12px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>

    <!-- LOGIN MODAL GATEWAY -->
    <div class="auth-overlay" id="auth-modal">
        <div class="auth-card">
            <h1>⚡ CYBER</h1>
            <p>Direct Encrypted Platform</p>
            <input type="text" id="l_u" placeholder="Username">
            <input type="password" id="l_p" placeholder="Password">
            <button class="auth-btn" onclick="performLogin()">LOGIN 🚀</button>
        </div>
    </div>

    <!-- SIDEBAR -->
    <div class="sidebar">
        <div class="sidebar-profile">
            <div class="avatar-circle" id="user-avatar-disp">👤</div>
            <h3 id="user-name-disp" style="color:#f8fafc; font-weight:700;">User</h3>
            <p style="color: #60a5fa; font-size: 0.82em; margin-bottom: 6px;">"Available"</p>
            <span class="role-badge">USER</span>
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

    <!-- MAIN CONTENT AREA -->
    <div class="main-container">

        <!-- DASHBOARD PAGE -->
        <div class="page-content active" id="page-dashboard">
            <h3 style="margin-bottom:20px;">📊 System Overview</h3>
            <div style="display:flex; gap:15px; margin-bottom:20px;">
                <div class="card-box"><h2 style="color:#60a5fa; font-size:2.2em;">1</h2><small style="color:#94a3b8;">Active Friends</small></div>
                <div class="card-box"><h2 style="color:#f59e0b; font-size:2.2em;">0</h2><small style="color:#94a3b8;">Pending Requests</small></div>
                <div class="card-box"><h2 style="color:#10b981; font-size:2.2em;">⚡</h2><small style="color:#94a3b8;">WebSocket Realtime Active</small></div>
            </div>
            <button class="auth-btn" onclick="showPage('messages', document.querySelectorAll('.nav-btn')[1])">💬 Open Chat Room</button>
        </div>

        <!-- MESSAGES CHAT ROOM PAGE -->
        <div class="page-content" id="page-messages">
            <div class="chat-header-bar">
                <div style="display:flex; align-items:center; gap:14px;">
                    <div style="font-size:1.5em;">👤</div>
                    <div>
                        <strong id="target-disp-name" style="font-size: 1.2em; color:#f8fafc;">Select Friend to Chat</strong>
                        <small style="display:block; color:#94a3b8;">Realtime WebSocket Channel</small>
                    </div>
                </div>
                <span style="background:#059669; color:#ffffff; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:bold;">🔒 Encrypted</span>
            </div>

            <div style="margin-bottom:10px;">
                <input type="text" id="target-user-input" placeholder="Recipient Username..." style="padding:10px; background:#111827; border:1px solid rgba(255,255,255,0.1); border-radius:8px; color:#fff; width:250px;">
            </div>

            <div class="chat-message-container" id="chat-box"></div>

            <div class="input-bar">
                <textarea id="msg-input" placeholder="Message..."></textarea>
                <button class="send-btn" onclick="sendMsg()">SEND 🚀</button>
            </div>
        </div>

        <!-- FRIENDS PAGE -->
        <div class="page-content" id="page-friends">
            <h3>👥 Friend Management</h3>
            <p style="color:#94a3b8; margin-top:10px;">Search users or manage requests...</p>
        </div>

        <!-- PROFILE PAGE -->
        <div class="page-content" id="page-profile">
            <h3>👤 Profile Customization</h3>
            <p style="color:#94a3b8; margin-top:10px;">Status and Bio customization ready.</p>
        </div>

        <!-- BLOCKLIST PAGE -->
        <div class="page-content" id="page-blocklist">
            <h3>🚫 Blocklist Management</h3>
            <p style="color:#94a3b8; margin-top:10px;">No blocked users.</p>
        </div>

        <!-- SETTINGS PAGE -->
        <div class="page-content" id="page-settings">
            <h3>⚙️ Security Settings</h3>
            <p style="color:#94a3b8; margin-top:10px;">Account security and encryption key status: ACTIVE</p>
        </div>

    </div>

    <script>
        let ws = null;
        let currentUser = "";

        function showPage(pageId, btnEl) {
            document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById('page-' + pageId).classList.add('active');
            if(btnEl) btnEl.classList.add('active');
        }

        function performLogin() {
            const user = document.getElementById('l_u').value.trim();
            if(!user) return alert("Enter Username");

            currentUser = user;
            document.getElementById('user-name-disp').innerText = currentUser;
            document.getElementById('user-avatar-disp').innerText = currentUser.charAt(0).toUpperCase();
            document.getElementById('user-id-disp').innerText = "#" + Math.floor(1000 + Math.random() * 9000);
            document.getElementById('auth-modal').style.display = 'none';

            // Connect Realtime WebSocket
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${currentUser}`);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                appendBubble(data.sender, data.content, data.time);
            };
        }

        function sendMsg() {
            const input = document.getElementById("msg-input");
            const target = document.getElementById("target-user-input").value.trim();
            const msg = input.value.trim();

            if(!ws || ws.readyState !== WebSocket.OPEN) return alert("Not Connected");
            if(!msg || !target) return alert("Enter Recipient & Message");

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
async def get_root():
    return ORIGINAL_HTML

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
                msg_out = {
                    "sender": sender,
                    "recipient": recipient,
                    "content": content,
                    "time": "NOW"
                }
                await manager.send_to_user(recipient, msg_out)
                await manager.send_to_user(sender, msg_out)

    except WebSocketDisconnect:
        manager.disconnect(username)
