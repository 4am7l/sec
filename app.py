from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
import secrets
from cryptography.fernet import Fernet
from supabase import create_client, Client

app = FastAPI()

# --- SUPABASE SETUP ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://shgxaxtjurbvbqdvmkzt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_FEE0CeWycaYbelk2VZPTBw_8j7lkftq")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ENCRYPTION SETUP ---
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

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ CYBER MESSENGER - INSTANT</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: #090d16; color: #f1f5f9; display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 280px; background: #111827; border-right: 1px solid rgba(255,255,255,0.08); padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .logo { font-size: 1.4em; font-weight: 800; color: #3b82f6; text-align: center; margin-bottom: 10px; }
        .user-box { background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.05); padding: 12px; border-radius: 12px; text-align: center; }
        .chat-area { flex: 1; display: flex; flex-direction: column; background: #090d16; }
        .chat-header { background: #111827; padding: 16px 24px; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; }
        .status-badge { background: #059669; color: #fff; padding: 4px 12px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
        .messages-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        .msg-wrapper { display: flex; width: 100%; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }
        .insta-bubble { max-width: 65%; padding: 12px 16px; border-radius: 18px; font-size: 0.95em; line-height: 1.45; box-shadow: 0 2px 10px rgba(0,0,0,0.25); word-wrap: break-word; }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #fff; border-bottom-right-radius: 4px; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; border-bottom-left-radius: 4px; border: 1px solid rgba(255,255,255,0.05); }
        .msg-time { font-size: 0.68em; opacity: 0.75; display: block; text-align: right; margin-top: 4px; }
        .input-bar { background: #111827; padding: 16px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; }
        .input-bar input { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px 16px; color: #fff; font-size: 0.95em; outline: none; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 24px; border-radius: 12px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="logo">⚡ CYBER MESSENGER</div>
        <div class="user-box">
            <input type="text" id="my-user" placeholder="Your Username" style="width:100%; padding:8px; background:#090d16; border:1px solid #334155; color:#fff; border-radius:8px; margin-bottom:8px;">
            <button onclick="connectWS()" style="width:100%; padding:8px; background:#2563eb; color:#fff; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">Connect 🚀</button>
        </div>
        <div style="margin-top: 20px;">
            <label style="font-size:0.8em; color:#94a3b8;">Chatting With:</label>
            <input type="text" id="target-user" placeholder="Recipient Username" style="width:100%; padding:8px; background:#090d16; border:1px solid #334155; color:#fff; border-radius:8px; margin-top:4px;">
        </div>
    </div>
    <div class="chat-area">
        <div class="chat-header">
            <div><strong id="header-target" style="font-size: 1.1em;">Select User to Chat</strong></div>
            <span class="status-badge">⚡ Instant WebSocket</span>
        </div>
        <div class="messages-container" id="chat-box"></div>
        <div class="input-bar">
            <input type="text" id="msg-input" placeholder="Message..." onkeydown="if(event.key==='Enter') sendMsg()">
            <button class="send-btn" onclick="sendMsg()">SEND 🚀</button>
        </div>
    </div>
    <script>
        let ws = null;
        function connectWS() {
            const username = document.getElementById("my-user").value.trim();
            if(!username) return alert("Enter your username");
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${username}`);
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                appendBubble(data.sender, data.content, data.time);
            };
            alert("Connected as: " + username);
        }
        function sendMsg() {
            const input = document.getElementById("msg-input");
            const recipient = document.getElementById("target-user").value.trim();
            const msg = input.value.trim();
            if(!ws || ws.readyState !== WebSocket.OPEN) return alert("Click Connect first!");
            if(!msg || !recipient) return;
            ws.send(JSON.stringify({ recipient: recipient, message: msg }));
            input.value = "";
        }
        function appendBubble(sender, content, time) {
            const myUser = document.getElementById("my-user").value.trim();
            const isMine = (sender === myUser);
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

@app.get("/")
async def get_index():
    return HTMLResponse(content=HTML_CONTENT)

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
                msg_id = secrets.token_hex(8)
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
