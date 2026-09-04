from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import secrets
from cryptography.fernet import Fernet
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

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

# --- WEBSOCKET MANAGER FOR REALTIME ---
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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

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
                # تشفير الرسالة
                enc_content = cipher.encrypt(content.encode()).decode()
                msg_id = secrets.token_hex(8)

                # حفظ في قاعدة البيانات Supabase
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

                # بث فوري بـ 0 ملي ثانية عبر WebSocket
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
