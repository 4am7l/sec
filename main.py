import streamlit as st
import streamlit.components.v1 as components
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

def generate_user_id():
    raw = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"#{raw}"

def generate_recovery_key():
    raw = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "messages": [], "pinned": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("messages", [])
            data.setdefault("pinned", {})
            modified = False
            for username, udata in data["users"].items():
                udata.setdefault("role", "admin" if len(data["users"]) == 1 else "user")
                udata.setdefault("blocked", [])
                udata.setdefault("recovery_key", "")
                if "user_id" not in udata or not udata["user_id"]:
                    udata["user_id"] = generate_user_id()
                    modified = True
                udata.setdefault("friends", [])
                udata.setdefault("friend_requests", [])
                udata.setdefault("nicknames", {})
                udata.setdefault("avatar", "")
                udata.setdefault("status_text", "Available")
                udata.setdefault("status_icon", "🟢 Online")
                udata.setdefault("bio", "Hey there! I am using Secure Chat.")
            
            if modified:
                save_data(data)
            return data
    except Exception as e:
        st.error(f"Data read error: {e}")
        return {"users": {}, "messages": [], "pinned": {}}

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

def get_avatar_html(avatar_b64, size=45, status_icon="🟢"):
    if avatar_b64:
        img_html = f'<img src="data:image/png;base64,{avatar_b64}" style="width:{size}px; height:{size}px; border-radius:50%; object-fit:cover; border:2px solid #6366f1; box-shadow:0 0 10px rgba(99,102,241,0.5);">'
    else:
        img_html = f'<div style="width:{size}px; height:{size}px; border-radius:50%; background:linear-gradient(135deg, #4f46e5, #0f172a); color:#f8fafc; display:inline-flex; align-items:center; justify-content:center; font-weight:bold; border:2px solid #6366f1; font-size:{int(size/2.2)}px; box-shadow:0 0 10px rgba(99,102,241,0.5);">👤</div>'
    
    status_symbol = status_icon.split()[0] if status_icon else "🟢"
    return f'<div style="position:relative; display:inline-block; vertical-align:middle;">{img_html}<span style="position:absolute; bottom:0; right:0; font-size:{int(size/3.5)}px; background:#0b0f19; border-radius:50%; padding:2px; box-shadow:0 0 5px rgba(0,0,0,0.8);">{status_symbol}</span></div>'

def navigate_to(page_name, target_user=None):
    st.session_state.current_page = page_name
    st.session_state.nav_sel = page_name
    if target_user:
        st.session_state.selected_chat = target_user

st.set_page_config(page_title="Ultra Secure Cyber Chat", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Ultra Modern Glassmorphism Background */
    .stApp {
        background: radial-gradient(circle at 15% 15%, #1e1b4b 0%, #0b0f19 50%, #030712 100%);
        color: #f1f5f9;
    }

    /* Cyber Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    /* Glow Input Elements */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
        background: rgba(30, 41, 59, 0.6) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(8px) !important;
        transition: all 0.3s ease !important;
    }

    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #818cf8 !important;
        box-shadow: 0 0 15px rgba(129, 140, 248, 0.35) !important;
    }

    /* Gradient Glowing Buttons */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, rgba(99,102,241,0.2) 0%, rgba(168,85,247,0.2) 100%) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(129, 140, 248, 0.3) !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        backdrop-filter: blur(10px) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
    }

    .stButton>button:hover, .stDownloadButton>button:hover {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%) !important;
        border-color: #c084fc !important;
        color: #ffffff !important;
        transform: translateY(-2px) scale(1.01) !important;
        box-shadow: 0 8px 25px rgba(168, 85, 247, 0.4) !important;
    }

    /* Glassmorphism Cards */
    .card-box {
        background: rgba(17, 24, 39, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 22px;
        text-align: center;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }

    .card-box:hover {
        transform: translateY(-4px);
        border-color: rgba(129, 140, 248, 0.4);
    }

    .user-card {
        background: rgba(17, 24, 39, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }

    .user-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.2);
    }

    /* Modern Glass Header */
    .chat-header-bar {
        background: rgba(17, 24, 39, 0.7);
        padding: 16px 24px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
    }

    /* Chat Messages Layout */
    .chat-message-container {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 12px;
    }

    .message-row {
        display: flex;
        width: 100%;
        margin-bottom: 4px;
    }

    .message-row.sent {
        justify-content: flex-end;
    }

    .message-row.received {
        justify-content: flex-start;
    }

    .message-bubble {
        padding: 14px 18px;
        max-width: 70%;
        word-wrap: break-word;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(8px);
        position: relative;
    }

    .message-bubble.sent {
        background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
        color: #ffffff;
        border-radius: 20px 20px 4px 20px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .message-bubble.received {
        background: rgba(30, 41, 59, 0.8);
        color: #f1f5f9;
        border-radius: 20px 20px 20px 4px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .reply-quote {
        background: rgba(0, 0, 0, 0.25);
        border-left: 3px solid #c084fc;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.82em;
        margin-bottom: 8px;
        color: #e9d5ff;
    }

    .message-time {
        font-size: 0.68em;
        color: rgba(255, 255, 255, 0.6);
        display: block;
        text-align: right;
        margin-top: 6px;
    }

    .reactions-bar {
        display: flex;
        gap: 6px;
        margin-top: 8px;
    }

    .reaction-badge {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 3px 8px;
        font-size: 0.78em;
        color: #f1f5f9;
    }

    .pinned-banner {
        background: linear-gradient(90deg, rgba(88, 28, 135, 0.5) 0%, rgba(30, 27, 75, 0.5) 100%);
        border: 1px solid rgba(168, 85, 247, 0.4);
        padding: 10px 18px;
        border-radius: 12px;
        color: #f3e8ff;
        font-size: 0.9em;
        margin-bottom: 14px;
        backdrop-filter: blur(10px);
    }

    .recovery-info {
        background: rgba(15, 23, 42, 0.8);
        border-left: 4px solid #a855f7;
        padding: 16px;
        border-radius: 12px;
        margin-top: 14px;
        box-shadow: 0 4px 20px rgba(168, 85, 247, 0.15);
    }
</style>
""", unsafe_allow_html=True)

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "🏠 Dashboard"

if "selected_chat" not in st.session_state:
    st.session_state.selected_chat = None

if "reply_to_msg" not in st.session_state:
    st.session_state.reply_to_msg = None

data = load_data()

if not st.session_state.current_user:
    st.markdown("<h1 style='text-align: center; background: linear-gradient(135deg, #a855f7, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size:2.8em; font-weight:800; margin-bottom: 5px;'>⚡ CYBER SECURE CHAT</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; font-size:1.05em; margin-bottom: 40px;'>Encrypted Private Communications Platform</p>", unsafe_allow_html=True)
    col_main = st.columns([1, 2, 1])[1]
    
    with col_main:
        tab_login, tab_reg, tab_rec = st.tabs(["🔑 LOGIN", "📝 REGISTER", "🛠️ RECOVERY"])

        with tab_login:
            st.markdown("##### Account Access")
            u_in = st.text_input("Username", key="l_u")
            p_in = st.text_input("Password", type="password", key="l_p")
            
            if st.button("LOGIN 🚀", use_container_width=True):
                user = data["users"].get(u_in)
                if user and user["password"] == hash_data(p_in):
                    st.session_state.current_user = u_in
                    st.session_state.current_page = "🏠 Dashboard"
                    st.session_state.nav_sel = "🏠 Dashboard"
                    log_audit("LOGIN_SUCCESS", f"User '{u_in}' logged in.")
                    st.success(f"Welcome back, {u_in}!")
                    st.rerun()
                else:
                    log_audit("LOGIN_FAILED", f"Failed login for '{u_in}'.")
                    st.error("Invalid credentials.")

        with tab_reg:
            st.markdown("##### Create Account")
            r_u = st.text_input("Username", key="r_u")
            r_p = st.text_input("Password (8+ chars, letters & digits)", type="password", key="r_p")
            r_c = st.text_input("Confirm Password", type="password", key="r_c")

            if st.button("CREATE ACCOUNT ✨", use_container_width=True):
                v_u, m_u = is_valid_username(r_u)
                v_p, m_p = is_strong_password(r_p)

                if not v_u:
                    st.error(m_u)
                elif r_u in data["users"]:
                    st.error("Username already exists.")
                elif not v_p:
                    st.error(m_p)
                elif r_p != r_c:
                    st.error("Passwords do not match.")
                else:
                    rec_k = generate_recovery_key()
                    u_id = generate_user_id()
                    assigned_role = "admin" if len(data["users"]) == 0 else "user"

                    data["users"][r_u] = {
                        "password": hash_data(r_p),
                        "recovery_key": hash_data(rec_k),
                        "role": assigned_role,
                        "blocked": [],
                        "user_id": u_id,
                        "friends": [],
                        "friend_requests": [],
                        "nicknames": {},
                        "avatar": "",
                        "status_text": "Available",
                        "status_icon": "🟢 Online",
                        "bio": "Hey there! I am using Secure Chat."
                    }
                    save_data(data)
                    log_audit("REGISTER_SUCCESS", f"User '{r_u}' registered.")

                    st.success("Account created successfully!")
                    st.markdown(f"""
                    <div class="recovery-info">
                        <strong>YOUR PERMANENT ID:</strong> <code>{u_id}</code><br>
                        <strong>SAVE RECOVERY KEY:</strong> <code>{rec_k}</code>
                    </div>
                    """, unsafe_allow_html=True)

        with tab_rec:
            st.markdown("##### Reset Password")
            f_u = st.text_input("Username", key="f_u")
            f_k = st.text_input("Recovery Key", key="f_k")
            f_p = st.text_input("New Password", type="password", key="f_p")
            f_c = st.text_input("Confirm New Password", type="password", key="f_c")

            if st.button("RESET PASSWORD 🔐", use_container_width=True):
                user_rec = data["users"].get(f_u)
                if not user_rec or hash_data(f_k) != user_rec.get("recovery_key"):
                    st.error("Invalid username or recovery key.")
                else:
                    v_p, m_p = is_strong_password(f_p)
                    if not v_p:
                        st.error(m_p)
                    elif f_p != f_c:
                        st.error("Passwords do not match.")
                    else:
                        user_rec["password"] = hash_data(f_p)
                        save_data(data)
                        log_audit("RECOVERY_SUCCESS", f"Password reset for '{f_u}'.")
                        st.success("Password reset successfully!")

else:
    current_user = st.session_state.current_user
    user_info = data["users"].get(current_user, {})
    role = user_info.get("role", "user")
    user_id = user_info.get("user_id", "#0000")
    avatar_b64 = user_info.get("avatar", "")
    status_icon = user_info.get("status_icon", "🟢 Online")
    status_text = user_info.get("status_text", "Available")
    user_bio = user_info.get("bio", "")
    my_nicknames = user_info.get("nicknames", {})

    sidebar_profile = f'<div style="text-align: center; padding: 12px 0;">{get_avatar_html(avatar_b64, size=85, status_icon=status_icon)}<h3 style="margin-top: 12px; margin-bottom: 2px; color:#f8fafc; font-weight:700;">{current_user}</h3><p style="color: #c084fc; font-size: 0.82em; margin-bottom: 6px;">"{status_text}"</p><span style="background:linear-gradient(135deg, #4f46e5, #9333ea); color:#ffffff; padding:3px 10px; border-radius:12px; font-size:0.75em; font-weight:bold; box-shadow:0 0 10px rgba(147, 51, 234, 0.4);">{role.upper()}</span></div>'
    st.sidebar.markdown(sidebar_profile, unsafe_allow_html=True)
    
    st.sidebar.markdown("<small style='color:#94a3b8;'>Your Permanent ID:</small>", unsafe_allow_html=True)
    st.sidebar.code(user_id, language=None)
    st.sidebar.markdown("---")

    menu_opts = ["🏠 Dashboard", "💬 Messages", "👥 Friends", "👤 Profile", "🚫 Blocklist", "⚙️ Settings"]
    if role == "admin":
        menu_opts.append("📊 Admin Panel")

    if "nav_sel" not in st.session_state:
        st.session_state.nav_sel = st.session_state.current_page

    def on_nav_change():
        st.session_state.current_page = st.session_state.nav_sel

    st.sidebar.radio("NAVIGATION", menu_opts, key="nav_sel", on_change=on_nav_change)

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.current_page = "🏠 Dashboard"
        st.session_state.nav_sel = "🏠 Dashboard"
        st.rerun()

    if st.session_state.current_page == "🏠 Dashboard":
        st.markdown("### 📊 System Overview")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown(f"""
            <div class="card-box">
                <h2 style="color:#c084fc; margin:0; font-size:2.2em; font-weight:800;">{len(user_info.get('friends', []))}</h2>
                <small style="color:#94a3b8; font-size:0.9em;">Active Friends</small>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div class="card-box">
                <h2 style="color:#f59e0b; margin:0; font-size:2.2em; font-weight:800;">{len(user_info.get('friend_requests', []))}</h2>
                <small style="color:#94a3b8; font-size:0.9em;">Pending Requests</small>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            my_count = sum(1 for m in data['messages'] if m.get('to') == current_user or m.get('from') == current_user)
            st.markdown(f"""
            <div class="card-box">
                <h2 style="color:#34d399; margin:0; font-size:2.2em; font-weight:800;">{my_count}</h2>
                <small style="color:#94a3b8; font-size:0.9em;">Encrypted Messages</small>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.button("💬 Open Chat Room", use_container_width=True, on_click=navigate_to, args=("💬 Messages",))

    elif st.session_state.current_page == "👥 Friends":
        st.markdown("### 👥 Friend Management")
        
        c_ref1, c_ref2 = st.columns([3, 1])
        with c_ref2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.rerun()

        t_search, t_my_friends, t_requests = st.tabs(["🔍 Search & Add", "👥 My Friends", "📩 Requests"])

        with t_search:
            s_query = st.text_input("Search user by Username or ID (e.g. #A123)", key="s_query_key")
            if s_query:
                found = False
                clean_q = s_query.strip()
                for uname, udata in data["users"].items():
                    if uname != current_user and (clean_q.lower() == uname.lower() or clean_q.upper() == udata.get("user_id")):
                        found = True
                        u_av = udata.get("avatar", "")
                        u_id_val = udata.get("user_id", "")
                        u_st_icon = udata.get("status_icon", "🟢")
                        u_bio = udata.get("bio", "")

                        col_card, col_action = st.columns([3, 1])
                        with col_card:
                            search_card_html = f'<div class="user-card"><div style="display:flex; align-items:center; gap:14px;">{get_avatar_html(u_av, size=52, status_icon=u_st_icon)}<div><strong style="font-size:1.15em; color:#f8fafc;">{uname}</strong><span style="color:#a855f7; font-size:0.88em; margin-left:6px;">({u_id_val})</span><p style="color:#94a3b8; font-size:0.82em; margin:2px 0 0 0;">{u_bio}</p></div></div></div>'
                            st.markdown(search_card_html, unsafe_allow_html=True)

                        with col_action:
                            if uname in user_info.get("friends", []):
                                st.info("Friends ✅")
                            elif current_user in udata.get("friend_requests", []):
                                st.info("Pending ⏳")
                            else:
                                if st.button(f"➕ Send Request", key=f"req_{uname}", use_container_width=True):
                                    fresh_data = load_data()
                                    fresh_data["users"][uname].setdefault("friend_requests", [])
                                    if current_user not in fresh_data["users"][uname]["friend_requests"]:
                                        fresh_data["users"][uname]["friend_requests"].append(current_user)
                                        save_data(fresh_data)
                                        log_audit("FRIEND_REQUEST_SENT", f"'{current_user}' sent request to '{uname}'.")
                                    st.success(f"Request sent to {uname}!")
                                    st.rerun()

                if not found:
                    st.warning("No user found with that Username or ID.")

        with t_my_friends:
            my_f_list = user_info.get("friends", [])
            if not my_f_list:
                st.info("No friends added yet.")
            else:
                for f_item in my_f_list:
                    f_udata = data["users"].get(f_item, {})
                    f_av = f_udata.get("avatar", "")
                    f_id = f_udata.get("user_id", "")
                    f_st_icon = f_udata.get("status_icon", "🟢")
                    f_st_txt = f_udata.get("status_text", "")
                    display_nick = my_nicknames.get(f_item, "")
                    label_str = f"{display_nick} ({f_item})" if display_nick else f_item

                    friend_card_html = f'<div class="user-card"><div style="display:flex; align-items:center; gap:14px;">{get_avatar_html(f_av, size=48, status_icon=f_st_icon)}<div><strong style="font-size:1.1em; color:#f8fafc;">{label_str}</strong><span style="color:#94a3b8; font-size:0.82em; margin-left:6px;">({f_id})</span><small style="display:block; color:#c084fc; font-size:0.78em;">{f_st_txt}</small></div></div></div>'
                    st.markdown(friend_card_html, unsafe_allow_html=True)

                    c_act1, c_act2, c_act3, c_act4 = st.columns([1, 1.2, 1, 1])
                    
                    with c_act1:
                        st.button(f"💬 Chat", key=f"chat_btn_{f_item}", use_container_width=True, on_click=navigate_to, args=("💬 Messages", f_item))

                    with c_act2:
                        with st.popover("✏️ Nickname", use_container_width=True):
                            new_nick = st.text_input(f"Set Nickname for {f_item}", value=display_nick, key=f"nick_input_{f_item}")
                            if st.button("Save", key=f"save_nick_{f_item}"):
                                fresh_data = load_data()
                                fresh_data["users"][current_user].setdefault("nicknames", {})[f_item] = new_nick.strip()
                                save_data(fresh_data)
                                st.rerun()

                    with c_act3:
                        if st.button(f"🗑️ Unfriend", key=f"unf_{f_item}", use_container_width=True):
                            fresh_data = load_data()
                            if f_item in fresh_data["users"][current_user].get("friends", []):
                                fresh_data["users"][current_user]["friends"].remove(f_item)
                            if current_user in fresh_data["users"][f_item].get("friends", []):
                                fresh_data["users"][f_item]["friends"].remove(current_user)
                            save_data(fresh_data)
                            log_audit("UNFRIEND", f"'{current_user}' unfriended '{f_item}'.")
                            st.rerun()

                    with c_act4:
                        if st.button(f"🚫 Block", key=f"block_f_{f_item}", use_container_width=True):
                            fresh_data = load_data()
                            fresh_data["users"][current_user].setdefault("blocked", [])
                            if f_item not in fresh_data["users"][current_user]["blocked"]:
                                fresh_data["users"][current_user]["blocked"].append(f_item)
                            if f_item in fresh_data["users"][current_user].get("friends", []):
                                fresh_data["users"][current_user]["friends"].remove(f_item)
                            if current_user in fresh_data["users"][f_item].get("friends", []):
                                fresh_data["users"][f_item]["friends"].remove(current_user)
                            save_data(fresh_data)
                            log_audit("USER_BLOCKED", f"'{current_user}' blocked '{f_item}'.")
                            st.rerun()

                    st.markdown("<hr style='border:0.5px solid rgba(255,255,255,0.08); margin: 12px 0;'>", unsafe_allow_html=True)

        with t_requests:
            fresh_user_info = data["users"].get(current_user, {})
            requests = fresh_user_info.get("friend_requests", [])
            if not requests:
                st.info("No pending friend requests.")
            else:
                for req_user in requests:
                    req_udata = data["users"].get(req_user, {})
                    req_av = req_udata.get("avatar", "")
                    req_id = req_udata.get("user_id", "")

                    col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
                    with col_r1:
                        req_card_html = f'<div class="user-card"><div style="display:flex; align-items:center; gap:12px;">{get_avatar_html(req_av, size=42)}<div><strong style="color:#f8fafc;">{req_user}</strong><span style="color:#94a3b8; font-size:0.82em;">({req_id})</span></div></div></div>'
                        st.markdown(req_card_html, unsafe_allow_html=True)
                    with col_r2:
                        if st.button("ACCEPT ✅", key=f"acc_{req_user}", use_container_width=True):
                            fresh_data = load_data()
                            fresh_data["users"][current_user].setdefault("friends", []).append(req_user)
                            fresh_data["users"][req_user].setdefault("friends", []).append(current_user)
                            if req_user in fresh_data["users"][current_user].get("friend_requests", []):
                                fresh_data["users"][current_user]["friend_requests"].remove(req_user)
                            save_data(fresh_data)
                            log_audit("FRIEND_ACCEPT", f"'{current_user}' accepted '{req_user}'.")
                            st.success(f"Accepted {req_user}!")
                            st.rerun()
                    with col_r3:
                        if st.button("DECLINE ❌", key=f"dec_{req_user}", use_container_width=True):
                            fresh_data = load_data()
                            if req_user in fresh_data["users"][current_user].get("friend_requests", []):
                                fresh_data["users"][current_user]["friend_requests"].remove(req_user)
                                save_data(fresh_data)
                            st.rerun()

    elif st.session_state.current_page == "👤 Profile":
        st.markdown("### 👤 User Profile Customization")
        col_p1, col_p2 = st.columns([1, 2])
        
        with col_p1:
            st.markdown("##### Profile Avatar")
            st.markdown(get_avatar_html(avatar_b64, size=135, status_icon=status_icon), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            up_avatar = st.file_uploader("Upload Circular Avatar", type=["png", "jpg", "jpeg"])
            if up_avatar:
                img_bytes = up_avatar.read()
                b64_img = base64.b64encode(img_bytes).decode('utf-8')
                user_info["avatar"] = b64_img
                save_data(data)
                st.success("Avatar updated!")
                st.rerun()

        with col_p2:
            st.markdown("##### Custom Status & Bio")
            new_st_icon = st.selectbox("Status Indicator", ["🟢 Online", "🌙 Away", "⛔ Do Not Disturb", "🎮 Gaming", "💻 Coding"], index=["🟢 Online", "🌙 Away", "⛔ Do Not Disturb", "🎮 Gaming", "💻 Coding"].index(status_icon) if status_icon in ["🟢 Online", "🌙 Away", "⛔ Do Not Disturb", "🎮 Gaming", "💻 Coding"] else 0)
            new_st_txt = st.text_input("Custom Status Message", value=status_text)
            new_bio = st.text_area("About Me (Bio)", value=user_bio)

            if st.button("SAVE PROFILE CHANGES 💾", use_container_width=True):
                user_info["status_icon"] = new_st_icon
                user_info["status_text"] = new_st_txt.strip()
                user_info["bio"] = new_bio.strip()
                save_data(data)
                st.success("Profile details saved successfully!")
                st.rerun()

    elif st.session_state.current_page == "💬 Messages":
        my_friends = user_info.get("friends", [])

        if not my_friends:
            st.info("You have no added friends yet. Go to '👥 Friends' page to search and add friends!")
        else:
            col_contacts, col_chat = st.columns([1, 2.5])

            with col_contacts:
                st.markdown("##### 💬 Friends List")
                for f_name in my_friends:
                    f_udata = data["users"].get(f_name, {})
                    f_avatar = f_udata.get("avatar", "")
                    f_st = f_udata.get("status_icon", "🟢")
                    f_nick = my_nicknames.get(f_name, f_name)
                    is_sel = (st.session_state.selected_chat == f_name)
                    
                    btn_label = f"{f_st.split()[0]} {f_nick}"
                    if is_sel:
                        btn_label = f"🔹 {btn_label}"

                    if st.button(btn_label, key=f"user_sel_{f_name}", use_container_width=True):
                        st.session_state.selected_chat = f_name
                        st.rerun()

            with col_chat:
                target_chat = st.session_state.selected_chat
                if not target_chat or target_chat not in my_friends:
                    st.info("👈 Select a friend from the left panel to start chatting.")
                else:
                    target_udata = data["users"].get(target_chat, {})
                    target_id = target_udata.get("user_id", "")
                    target_av = target_udata.get("avatar", "")
                    target_st_icon = target_udata.get("status_icon", "🟢")
                    target_st_txt = target_udata.get("status_text", "Available")
                    target_disp = my_nicknames.get(target_chat, target_chat)
                    
                    chat_header_html = f'<div class="chat-header-bar"><div style="display: flex; align-items: center; gap: 14px;">{get_avatar_html(target_av, size=46, status_icon=target_st_icon)}<div><strong style="font-size: 1.2em; color:#f8fafc;">{target_disp}</strong><span style="color: #c084fc; font-size: 0.88em; margin-left: 6px;">({target_chat} {target_id})</span><small style="display:block; color:#94a3b8; font-size: 0.8em;">{target_st_txt}</small></div></div><span style="background: linear-gradient(135deg, #059669, #10b981); color: #ffffff; padding: 5px 12px; border-radius: 12px; font-size: 0.75em; font-weight: bold; box-shadow:0 0 10px rgba(16,185,129,0.3);">🔒 AES-256</span></div>'
                    st.markdown(chat_header_html, unsafe_allow_html=True)

                    pair_key = f"{min(current_user, target_chat)}_{max(current_user, target_chat)}"
                    pinned_msg = data.get("pinned", {}).get(pair_key)
                    if pinned_msg:
                        st.markdown(f'<div class="pinned-banner">📌 <strong>Pinned Message:</strong> {pinned_msg}</div>', unsafe_allow_html=True)

                    chat_container = st.container(height=420)

                    @st.fragment(run_every="2s")
                    def render_live_chat():
                        live_data = load_data()
                        msgs_to_burn = []
                        
                        filtered_msgs = [
                            m for m in live_data["messages"]
                            if (m.get("from") == current_user and m.get("to") == target_chat) or
                               (m.get("from") == target_chat and m.get("to") == current_user)
                        ]
                        
                        with chat_container:
                            st.markdown('<div class="chat-message-container">', unsafe_allow_html=True)
                            for idx, m in enumerate(filtered_msgs):
                                f_user = m.get("from")
                                try:
                                    dec_raw = cipher.decrypt(m['content'].encode()).decode()
                                    txt_display = dec_raw
                                    file_bytes, file_name, file_mime = None, None, None

                                    if "[FILE:" in dec_raw:
                                        parts = dec_raw.split("[FILE:")
                                        txt_display = parts[0].strip()
                                        meta_and_b64 = parts[1]
                                        meta_str = meta_and_b64.split("]")[0]
                                        b64_str = meta_and_b64.split("]")[1]
                                        
                                        file_name, file_mime = meta_str.split(":", 1)
                                        file_bytes = base64.b64decode(b64_str)

                                except Exception:
                                    txt_display = "⚠️ <i>[Message decryption failed]</i>"
                                    file_bytes = None

                                is_mine = (f_user == current_user)
                                alignment = "sent" if is_mine else "received"
                                burn_html = '<span style="color:#f43f5e; margin-left:6px;" title="Burn on read">🔥</span>' if m.get("burn") else ""
                                time_str = m['time'].split(" ")[1][:5]
                                reply_text = m.get("reply")

                                st.markdown(f'<div class="message-row {alignment}">', unsafe_allow_html=True)
                                
                                with st.container():
                                    st.markdown(f'<div class="message-bubble {alignment}">', unsafe_allow_html=True)
                                    
                                    if reply_text:
                                        st.markdown(f'<div class="reply-quote">↩️ {reply_text}</div>', unsafe_allow_html=True)

                                    if txt_display:
                                        st.markdown(f'<div>{txt_display}{burn_html}</div>', unsafe_allow_html=True)

                                    if file_bytes:
                                        if file_mime and "image" in file_mime:
                                            st.image(file_bytes, caption=file_name, use_container_width=True)
                                        else:
                                            st.markdown(f"📄 **{file_name}**")

                                        st.download_button(
                                            label="⬇️ Download Attachment",
                                            data=file_bytes,
                                            file_name=file_name,
                                            mime=file_mime,
                                            key=f"dl_{m['time']}_{idx}",
                                            use_container_width=True
                                        )

                                    reactions = m.get("reactions", {})
                                    if reactions:
                                        r_html = "".join([f'<span class="reaction-badge">{emoji} {count}</span>' for emoji, count in reactions.items()])
                                        st.markdown(f'<div class="reactions-bar">{r_html}</div>', unsafe_allow_html=True)

                                    st.markdown(f'<span class="message-time">{time_str}</span>', unsafe_allow_html=True)
                                    st.markdown('</div>', unsafe_allow_html=True)

                                    with st.popover("⚡ Actions"):
                                        st.caption("Quick Reaction")
                                        rc1, rc2, rc3, rc4 = st.columns(4)
                                        for em in ["❤️", "👍", "🔥", "😂"]:
                                            if rc1.button(em, key=f"react_{idx}_{em}"):
                                                m.setdefault("reactions", {})
                                                m["reactions"][em] = m["reactions"].get(em, 0) + 1
                                                save_data(live_data)
                                                st.rerun()

                                        if st.button("↩️ Reply", key=f"rpl_btn_{idx}"):
                                            st.session_state.reply_to_msg = txt_display[:30] if txt_display else "File Attachment"
                                            st.rerun()

                                        if st.button("📌 Pin Message", key=f"pin_btn_{idx}"):
                                            live_data.setdefault("pinned", {})[pair_key] = txt_display[:50]
                                            save_data(live_data)
                                            st.rerun()

                                st.markdown('</div>', unsafe_allow_html=True)

                                if not is_mine and m.get("burn"):
                                    msgs_to_burn.append(m)

                            st.markdown('</div><div id="end-of-chat"></div>', unsafe_allow_html=True)
                            
                            components.html("""
                            <script>
                                function scrollToBottom() {
                                    var element = window.parent.document.getElementById("end-of-chat");
                                    if (element) {
                                        element.scrollIntoView({ behavior: "smooth", block: "end" });
                                    }
                                }
                                setTimeout(scrollToBottom, 300);
                            </script>
                            """, height=0)

                        if msgs_to_burn:
                            for bm in msgs_to_burn:
                                live_data["messages"].remove(bm)
                                log_audit("MESSAGE_BURNED", f"Burned msg from '{bm['from']}' to '{bm['to']}'.")
                            save_data(live_data)

                    render_live_chat()

                    st.markdown("<div style='clear:both; margin-top:10px;'></div>", unsafe_allow_html=True)

                    if st.session_state.reply_to_msg:
                        st.info(f"↩️ Replying to: *{st.session_state.reply_to_msg}*")

                    with st.form(key="send_form", clear_on_submit=True, border=True):
                        in_msg = st.text_area("Message", placeholder="Type a secure message...", key="in_msg_key", label_visibility="collapsed", height=68)
                        
                        c_file, c_chk, c_btn = st.columns([2, 1, 1])
                        with c_file:
                            up_file = st.file_uploader("Attach", type=["png", "jpg", "jpeg", "pdf", "txt"], label_visibility="collapsed")
                        with c_chk:
                            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                            chk_burn = st.checkbox("🔥 Burn")
                        with c_btn:
                            st.markdown("<div style='margin-top:5px;'></div>", unsafe_allow_html=True)
                            btn_sub = st.form_submit_button("SEND 🚀", use_container_width=True)

                        if btn_sub:
                            fresh_data = load_data()
                            recipient_blocked = fresh_data["users"][target_chat].get("blocked", [])
                            if current_user in recipient_blocked:
                                st.error("User has blocked you.")
                            elif not in_msg.strip() and not up_file:
                                st.warning("Cannot send an empty message.")
                            else:
                                final_payload = in_msg.strip()
                                
                                if up_file:
                                    f_bytes = up_file.read()
                                    b64_data = base64.b64encode(f_bytes).decode('utf-8')
                                    file_meta = f"[FILE:{up_file.name}:{up_file.type}]{b64_data}"
                                    final_payload = f"{final_payload}\n{file_meta}" if final_payload else file_meta

                                enc_content = cipher.encrypt(final_payload.encode()).decode()
                                new_msg_obj = {
                                    "id": secrets.token_hex(6),
                                    "from": current_user,
                                    "to": target_chat,
                                    "content": enc_content,
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "burn": chk_burn,
                                    "reply": st.session_state.reply_to_msg,
                                    "reactions": {}
                                }
                                fresh_data["messages"].append(new_msg_obj)
                                save_data(fresh_data)
                                log_audit("MESSAGE_SENT", f"From '{current_user}' to '{target_chat}'.")
                                st.session_state.reply_to_msg = None
                                st.rerun()

    elif st.session_state.current_page == "🚫 Blocklist":
        st.markdown("### 🚫 Blocklist Management")
        block_list = data["users"][current_user].setdefault("blocked", [])
        st.write(f"Currently Blocked Users: `{', '.join(block_list) if block_list else 'None'}`")
        
        targets = [u for u in data["users"] if u != current_user]
        if targets:
            t_user = st.selectbox("Select Target User", targets)
            b_col1, b_col2 = st.columns(2)
            
            with b_col1:
                if st.button("BLOCK USER 🚫", use_container_width=True) and t_user not in block_list:
                    block_list.append(t_user)
                    save_data(data)
                    log_audit("USER_BLOCKED", f"'{current_user}' blocked '{t_user}'.")
                    st.success(f"Blocked {t_user}.")
                    st.rerun()
            
            with b_col2:
                if st.button("UNBLOCK USER ✅", use_container_width=True) and t_user in block_list:
                    block_list.remove(t_user)
                    save_data(data)
                    log_audit("USER_UNBLOCKED", f"'{current_user}' unblocked '{t_user}'.")
                    st.success(f"Unblocked {t_user}.")
                    st.rerun()

    elif st.session_state.current_page == "⚙️ Settings":
        st.markdown("### ⚙️ Account Security Settings")
        st.write(f"Logged in as: **{current_user}**")
        
        curr_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        conf_pwd = st.text_input("Confirm Password", type="password")

        if st.button("UPDATE PASSWORD 🔑", use_container_width=True):
            if hash_data(curr_pwd) != data["users"][current_user]["password"]:
                st.error("Current password incorrect.")
            else:
                v_p, m_p = is_strong_password(new_pwd)
                if not v_p:
                    st.error(m_p)
                elif new_pwd != conf_pwd:
                    st.error("Passwords do not match.")
                else:
                    data["users"][current_user]["password"] = hash_data(new_pwd)
                    save_data(data)
                    log_audit("PASSWORD_CHANGE", f"User '{current_user}' updated password.")
                    st.success("Password updated successfully!")

    elif st.session_state.current_page == "📊 Admin Panel":
        st.markdown("### 📊 Admin Panel")
        st.markdown("##### Registered User Accounts")
        st.table([{"User": u, "ID": info.get("user_id"), "Role": info.get("role"), "Status": info.get("status_icon"), "Friends": len(info.get("friends", []))} for u, info in data["users"].items()])
        
        st.markdown("##### Recent Audit Logs")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                st.code("".join(f.readlines()[-20:]))
        else:
            st.info("No audit logs found.")
