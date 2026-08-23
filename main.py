import streamlit as st
import json
import os
import hashlib
import secrets
import string
import base64
from datetime import datetime
from cryptography.fernet import Fernet

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
KEY_FILE = os.path.join(os.path.dirname(__file__), "secret.key")
LOG_FILE = os.path.join(os.path.dirname(__file__), "audit.log")

def log_audit(event_type, details):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{event_type}] {details}\n")
    except Exception as e:
        st.error(f"Audit logging error: {e}")

def load_or_generate_key():
    try:
        if not os.path.exists(KEY_FILE):
            key = Fernet.generate_key()
            with open(KEY_FILE, "wb") as f:
                f.write(key)
            return key
        with open(KEY_FILE, "rb") as f:
            return f.read()
    except Exception as e:
        st.error(f"Encryption key error: {e}")
        st.stop()

SECRET_KEY = load_or_generate_key()
cipher = Fernet(SECRET_KEY)

def hash_data(value):
    return hashlib.sha256(value.encode()).hexdigest()

def generate_recovery_key():
    raw = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "messages": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("messages", [])
            for username, udata in data["users"].items():
                udata.setdefault("role", "admin" if len(data["users"]) == 1 else "user")
                udata.setdefault("blocked", [])
                udata.setdefault("recovery_key", "")
            return data
    except Exception as e:
        st.error(f"Data read error: {e}")
        return {"users": {}, "messages": []}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        st.error(f"Data save error: {e}")

def is_valid_username(username):
    if not (3 <= len(username) <= 20):
        return False, "Username must be 3-20 characters long."
    if not all(c.isalnum() or c == '_' for c in username):
        return False, "Username allows letters, numbers, and underscores (_)."
    return True, ""

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        return False, "Password must contain both letters and digits."
    return True, ""

st.set_page_config(page_title="Secure Chat App", page_icon="🔒", layout="wide")

st.markdown("""
<style>
    /* Dark Slate & Matte Black Professional Theme */
    .stApp {
        background-color: #090a0f;
        color: #d1d5db;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #111318 !important;
        border-right: 1px solid #1f232c !important;
    }

    /* Inputs Styling */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
        background-color: #16181d !important;
        color: #f3f4f6 !important;
        border: 1px solid #282c37 !important;
        border-radius: 6px !important;
    }
    
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #4b5563 !important;
        box-shadow: none !important;
    }

    /* Buttons Styling */
    .stButton>button, .stDownloadButton>button {
        background-color: #1f232c !important;
        color: #e5e7eb !important;
        border: 1px solid #374151 !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    .stButton>button:hover, .stDownloadButton>button:hover {
        background-color: #374151 !important;
        border-color: #4b5563 !important;
        color: #ffffff !important;
    }

    /* Clean Chat Component */
    .chat-header-bar {
        background-color: #111318;
        padding: 12px 18px;
        border-radius: 8px;
        border: 1px solid #1f232c;
        margin-bottom: 15px;
    }

    .bubble-sent {
        background-color: #282c37;
        color: #f3f4f6;
        padding: 10px 14px;
        border-radius: 12px 12px 2px 12px;
        margin: 6px 0;
        max-width: 75%;
        float: right;
        clear: both;
        border: 1px solid #374151;
        word-wrap: break-word;
    }

    .bubble-received {
        background-color: #16181d;
        color: #d1d5db;
        padding: 10px 14px;
        border-radius: 12px 12px 12px 2px;
        margin: 6px 0;
        max-width: 75%;
        float: left;
        clear: both;
        border: 1px solid #282c37;
        word-wrap: break-word;
    }

    .bubble-time {
        font-size: 0.7em;
        color: #9ca3af;
        margin-top: 4px;
        display: block;
        text-align: right;
    }

    .card-box {
        background-color: #111318;
        border: 1px solid #1f232c;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }

    .recovery-info {
        background-color: #16181d;
        border-left: 3px solid #6b7280;
        padding: 12px;
        border-radius: 4px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

if "selected_chat" not in st.session_state:
    st.session_state.selected_chat = None

data = load_data()

st.markdown("<h2 style='text-align: center; color: #e5e7eb;'>🔒 SECURE CHAT APPLICATION</h2>", unsafe_allow_html=True)

if not st.session_state.current_user:
    col_main = st.columns([1, 2, 1])[1]
    
    with col_main:
        tab_login, tab_reg, tab_rec = st.tabs(["🔑 LOGIN", "📝 REGISTER", "🛠️ RECOVERY"])

        with tab_login:
            st.markdown("##### Account Access")
            u_in = st.text_input("Username", key="l_u")
            p_in = st.text_input("Password", type="password", key="l_p")
            
            if st.button("LOGIN", use_container_width=True):
                user = data["users"].get(u_in)
                if user and user["password"] == hash_data(p_in):
                    st.session_state.current_
