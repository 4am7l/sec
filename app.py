from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
import secrets

app = FastAPI()

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

# --- HTML / CSS / JS UI ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ CYBER MESSENGER - PRO</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: #090d16; color: #f1f5f9; display: flex; height: 100vh; overflow: hidden; }

        /* Login Modal */
        .auth-overlay { position: fixed; inset: 0; background: rgba(9, 13, 22, 0.95); backdrop-filter: blur(10px); display: flex; align-items: center; justify-content: center; z-index: 999; }
        .auth-card { background: #111827; border: 1px solid rgba(255,255,255,0.1); padding: 35px; border-radius: 20px; width: 380px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .auth-card h2 { color: #3b82f6; margin-bottom: 20px; font-size: 1.6em; }
        .auth-card input { width: 100%; padding: 12px; margin-bottom: 12px; background: #090d16; border: 1px solid #334155; border-radius: 10px; color: #fff; outline: none; font-size: 0.95em; }
        .auth-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; transition: 0.2s; margin-top: 5px; }
        .auth-btn:hover { transform: scale(1.02); }

        /* Layout */
        .sidebar { width: 300px; background: #111827; border-right: 1px solid rgba(255,255,255,0.08); padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .logo { font-size: 1.5em; font-weight: 800; color: #3b82f6; text-align: center; }
        .profile-card { background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.08); padding: 15px; border-radius: 14px; display: flex; align-items: center; gap: 12px; }
        .avatar { width: 42px; height: 42px; background: #3b82f6; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.2em; }
        
        .chat-area { flex: 1; display: flex; flex-direction: column; background: #090d16; }
        .chat-header { background: #111827; padding: 16px 24px; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; }
        .status-badge { background: #059669; color: #fff; padding: 5px 14px; border-radius: 20px; font-size: 0.75em; font-weight: bold; }

        .messages-container { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 14px; }
        .msg-wrapper { display: flex; width: 100%; }
        .msg-wrapper.sent { justify-content: flex-end; }
        .msg-wrapper.received { justify-content: flex-start; }

        .insta-bubble { max-width: 60%; padding: 12px 18px; border-radius: 18px; font-size: 0.95em; line-height: 1.5; box-shadow: 0 4px 15px rgba(0,0,0,0.2); word-wrap: break-word; }
        .sent .insta-bubble { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #fff; border-bottom-right-radius: 4px; }
        .received .insta-bubble { background: #1e293b; color: #f1f5f9; border-bottom-left-radius: 4px; border: 1px solid rgba(255,255,255,0.05); }
        .msg-time { font-size: 0.65em; opacity: 0.7; display: block; text-align: right; margin-top: 4px; }

        .input-bar { background: #111827; padding: 18px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; }
        .input-bar input { flex: 1; background: #090d16; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 14px 18px; color: #fff; outline: none; font-size: 0.95em; }
        .send-btn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; padding: 0 28px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .block-btn { background: #ef4444; color: #fff; border: none; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.8em; font-weight: bold; cursor: pointer; margin-top: 6px; }
    </style>
</head>
<body>

    <div class="auth-overlay" id="auth-modal">
        <div class="auth-card">
            <h2>⚡ CYBER AUTH</h2>
            <input type="text" id="user-id-input" placeholder="Username / User ID">
            <input type="password" id="user-pass-input" placeholder="Password">
            <button class="auth-btn" onclick="startApp()">Login & Connect 🚀</button>
            <div id="rec-key" style="margin-top:15px; font-size:0.75em; color:#10b981; word-break:break-all;"></div>
        </div>
    </div>

    <div class="sidebar">
        <div class="logo">⚡ CYBER MESSENGER</div>
        <div class="profile-card">
            <div class="avatar" id="my-avatar">U</div>
            <div>
                <strong id="display-my-id" style="font-size: 0.9em; color: #f8fafc;">Offline</strong>
                <p style="font-size: 0.7em; color: #10b981;">● Active Session</p>
            </div>
        </div>
        <div style="margin-top: 15px;">
            <label style="font-size:0.8em; color:#94a3b8; font-weight:600;">Recipient Username:</label>
            <input type="text" id="target-id-input" placeholder="Target Username" style="width:100%; padding:10px; background:#090d16; border:1px solid #334155; color:#fff; border-radius:10px; margin-top:6px; outline:none;">
            <button class="block-btn" onclick="alert('User Blocked 🚫')">Block User 🚫</button>
        </div>
    </div>

    <div class="chat-area">
        <div class="chat-header">
            <div><strong style="font-size: 1.1em;">Encrypted Live Room</strong></div>
            <span class="status-badge">⚡ Realtime WebSocket</span>
        </div>
        <div class="messages-container" id="chat-box"></div>
        <div class="input-bar">
            <input type="text" id="msg-input" placeholder="Type a message..." onkeydown="if(event.key==='Enter') sendMsg()">
            <button class="send-btn" onclick="sendMsg()">SEND 🚀</button>
        </div>
    </div>

    <script>
        let ws = null;
        let myUserId = "";

        function startApp() {
            const inputVal = document.getElementById("user-id-input").value.trim();
            if(!inputVal) return alert("Enter Username");
            
            myUserId = inputVal;
            document.getElementById("display-my-id").innerText = myUserId;
            document.getElementById("my-avatar").innerText = myUserId.charAt(0).toUpperCase();
            document.getElementById("auth-modal").style.display = "none";
            document.getElementById("rec-key").innerText = "RECOVERY KEY: REC-" + Math.random().toString(36).substring(2, 10).toUpperCase();

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${myUserId}`);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                appendBubble(data.sender_id, data.content, data.time);
            };
        }

        function sendMsg() {
            const input = document.getElementById("msg-input");
            const receiverId = document.getElementById("target-id-input").value.trim();
            const msg = input.value.trim();

            if(!ws || ws.readyState !== WebSocket.OPEN) return alert("Not Connected");
            if(!msg || !receiverId) return alert("Enter recipient & message");

            ws.send(JSON.stringify({
                receiver_id: receiverId,
                content: msg
            }));

            input.value = "";
        }

        function appendBubble(senderId, content, time) {
            const isMine = (senderId === myUserId);
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
async def read_root():
    return HTML_LAYOUT

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            receiver_id = data.get("receiver_id")
            content = data.get("content")

            if content and receiver_id:
                msg_out = {
                    "sender_id": user_id,
                    "receiver_id": receiver_id,
                    "content": content,
                    "time": "NOW"
                }
                await manager.send_to_user(receiver_id, msg_out)
                await manager.send_to_user(user_id, msg_out)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
