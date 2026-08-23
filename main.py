import streamlit as st
import os
import hashlib
import secrets
import string
import base64
from datetime import datetime
from cryptography.fernet import Fernet
from supabase import create_client, Client

# --- SETUP SUPABASE ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials missing! Please configure SUPABASE_URL and SUPABASE_KEY in secrets.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

KEY_FILE = os.path.join(os.path.dirname(__file__), "secret.key")

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

# --- SUPABASE OPS ---
def get_all_users():
    res = supabase.table("users").select("*").execute()
    return {row["username"]: row for row in res.data}

def get_user(username):
    res = supabase.table("users").select("*").eq("username", username).execute()
    return res.data[0] if res.data else None

def create_user(username, password_hash, recovery_hash, user_id, role="user"):
    payload = {
        "username": username,
        "password": password_hash,
        "recovery_key": recovery_hash,
        "role": role,
        "user_id": user_id,
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

def update_user_field(username, updates_dict):
    supabase.table("users").update(updates_dict).eq("username", username).execute()

def get_messages(user1, user2):
    res1 = supabase.table("messages").select("*").eq("sender", user1).eq("recipient", user2).execute().data
    res2 = supabase.table("messages").select("*").eq("sender", user2).eq("recipient", user1).execute().data
    all_msgs = res1 + res2
    all_msgs.sort(key=lambda x: x["created_at"])
    return all_msgs

def send_message(msg_id, sender, recipient, content_enc, burn=False, reply=None):
    payload = {
        "id": msg_id,
        "sender": sender,
        "recipient": recipient,
        "content": content_enc,
        "burn": burn,
        "reply": reply,
        "reactions": {}
    }
    supabase.table("messages").insert(payload).execute()

def delete_message(msg_id):
    supabase.table("messages").delete().eq("id", msg_id).execute()

def get_pinned(pair_key):
    res = supabase.table("pinned").select("content").eq("pair_key", pair_key).execute()
    return res.data[0]["content"] if res.data else None

def set_pinned(pair_key, content):
    supabase.table("pinned").upsert({"pair_key": pair_key, "content": content}).execute()

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

def get_avatar_html(avatar_b64, size=40):
    if avatar_b64:
        return f'<img src="data:image/png;base64,{avatar_b64}" style="width:{size}px; height:{size}px; border-radius:50%; object-fit:cover; border:2px solid #3b82f6;">'
    return f'<div style="width:{size}px; height:{size}px; border-radius:50%; background:#2563eb; color:#fff; display:inline-flex; align-items:center; justify-content:center; font-weight:bold; font-size:{int(size/2.2)}px;">👤</div>'

# --- SESSION & REFRESH PERSISTENCE ---
# حفظ المستخدم بالرابط لحمايته من الخروج عند الـ Refresh
if "user" in st.query_params:
    saved_user = st.query_params["user"]
    if "current_user" not in st.session_state or not st.session_state.current_user:
        u_data = get_user(saved_user)
        if u_data:
            st.session_state.current_user = saved_user

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "💬 Messages"

if "selected_chat" not in st.session_state:
    st.session_state.selected_chat = None

st.set_page_config(page_title="Ultra Messenger", page_icon="⚡", layout="wide")

# --- RESPONSIVE CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    * { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background: #0b0e14; color: #f3f4f6; }

    section[data-testid="stSidebar"] {
        background: #121824 !important;
        border-right: 1px solid #1f293d !important;
    }

    /* Chat Messages Layout */
    .chat-box {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px;
    }

    .msg-container {
        display: flex;
        width: 100%;
        margin-bottom: 4px;
    }

    .msg-container.sent { justify-content: flex-end; }
    .msg-container.received { justify-content: flex-start; }

    .bubble {
        max-width: 80%;
        padding: 10px 14px;
        border-radius: 18px;
        font-size: 0.93em;
        line-height: 1.4;
        word-break: break-word;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    }

    @media (max-width: 768px) {
        .bubble { max-width: 90%; }
    }

    .msg-container.sent .bubble {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #ffffff;
        border-bottom-right-radius: 4px;
    }

    .msg-container.received .bubble {
        background: #1e293b;
        color: #f1f5f9;
        border-bottom-left-radius: 4px;
        border: 1px solid #334155;
    }

    .msg-meta {
        font-size: 0.65em;
        opacity: 0.7;
        margin-top: 4px;
        text-align: right;
        display: block;
    }

    .reply-badge {
        background: rgba(0,0,0,0.25);
        border-left: 3px solid #60a5fa;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN SCREEN ---
if not st.session_state.current_user:
    st.markdown("<h1 style='text-align: center; color:#3b82f6;'>⚡ CYBER MESSENGER</h1>", unsafe_allow_html=True)
    col_main = st.columns([1, 2, 1])[1]
    
    with col_main:
        t_login, t_reg = st.tabs(["🔑 LOGIN", "📝 REGISTER"])

        with t_login:
            u_in = st.text_input("Username", key="l_u")
            p_in = st.text_input("Password", type="password", key="l_p")
            if st.button("LOGIN 🚀", use_container_width=True):
                user = get_user(u_in)
                if user and user["password"] == hash_data(p_in):
                    st.session_state.current_user = u_in
                    st.query_params["user"] = u_in # حفظ الجلسة في الرابط
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

        with t_reg:
            r_u = st.text_input("Username", key="r_u")
            r_p = st.text_input("Password", type="password", key="r_p")
            r_c = st.text_input("Confirm Password", type="password", key="r_c")

            if st.button("REGISTER ✨", use_container_width=True):
                v_u, m_u = is_valid_username(r_u)
                v_p, m_p = is_strong_password(r_p)

                if not v_u: st.error(m_u)
                elif get_user(r_u): st.error("User exists.")
                elif not v_p: st.error(m_p)
                elif r_p != r_c: st.error("Passwords mismatch.")
                else:
                    create_user(r_u, hash_data(r_p), hash_data(generate_recovery_key()), generate_user_id())
                    st.success("Account Created!")

# --- MAIN APP ---
else:
    current_user = st.session_state.current_user
    user_info = get_user(current_user)
    if not user_info:
        st.session_state.current_user = None
        st.query_params.clear()
        st.rerun()

    my_friends = user_info.get("friends", []) or []
    my_nicknames = user_info.get("nicknames", {}) or {}

    # Sidebar
    st.sidebar.markdown(f"<div style='text-align:center;'>{get_avatar_html(user_info.get('avatar'), 70)}<h3 style='margin:5px 0;'>{current_user}</h3></div>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.current_user = None
        st.query_params.clear()
        st.rerun()

    st.sidebar.markdown("---")
    page = st.sidebar.radio("MENU", ["💬 Messages", "👥 Friends", "👤 Profile"])

    if page == "👥 Friends":
        st.markdown("### 👥 Friends & Search")
        s_query = st.text_input("Search User", key="sq")
        if s_query:
            all_u = get_all_users()
            for u_name, u_data in all_u.items():
                if u_name != current_user and (s_query.lower() in u_name.lower() or s_query.upper() == u_data.get("user_id")):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"👤 **{u_name}** ({u_data.get('user_id')})")
                    if c2.button("Add", key=f"add_{u_name}"):
                        reqs = u_data.get("friend_requests", []) or []
                        if current_user not in reqs:
                            reqs.append(current_user)
                            update_user_field(u_name, {"friend_requests": reqs})
                            st.success("Sent!")

        st.markdown("#### Pending Requests")
        reqs = user_info.get("friend_requests", []) or []
        for r in reqs:
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"📩 {r}")
            if c2.button("Accept", key=f"acc_{r}"):
                my_f = user_info.get("friends", []) or []
                my_f.append(r)
                reqs.remove(r)
                update_user_field(current_user, {"friends": my_f, "friend_requests": reqs})
                
                their = get_user(r)
                tf = their.get("friends", []) or []
                tf.append(current_user)
                update_user_field(r, {"friends": tf})
                st.rerun()

    elif page == "👤 Profile":
        st.markdown("### 👤 Profile Settings")
        up_avatar = st.file_uploader("Change Avatar", type=["png", "jpg", "jpeg"])
        if up_avatar:
            b64_img = base64.b64encode(up_avatar.read()).decode('utf-8')
            update_user_field(current_user, {"avatar": b64_img})
            st.success("Updated!")
            st.rerun()

    elif page == "💬 Messages":
        if not my_friends:
            st.info("No friends added yet. Add friends from '👥 Friends' menu!")
        else:
            col_list, col_chat = st.columns([1, 2.5])

            with col_list:
                st.markdown("##### 💬 Chats")
                for f_name in my_friends:
                    f_nick = my_nicknames.get(f_name, f_name)
                    btn_style = f"🔹 {f_nick}" if st.session_state.selected_chat == f_name else f"👤 {f_nick}"
                    if st.button(btn_style, key=f"sel_{f_name}", use_container_width=True):
                        st.session_state.selected_chat = f_name
                        st.rerun()

            with col_chat:
                target_chat = st.session_state.selected_chat
                if not target_chat or target_chat not in my_friends:
                    st.info("👈 Select a friend to start chatting.")
                else:
                    target_udata = get_user(target_chat) or {}
                    target_disp = my_nicknames.get(target_chat, target_chat)

                    # Header
                    st.markdown(f"""
                    <div style="background:#121824; padding:10px 16px; border-radius:12px; display:flex; align-items:center; gap:10px; margin-bottom:10px; border:1px solid #1f293d;">
                        {get_avatar_html(target_udata.get('avatar'), 40)}
                        <div>
                            <strong style="font-size:1.1em;">{target_disp}</strong>
                            <small style="display:block; color:#9ca3af;">{target_chat} {target_udata.get('user_id', '')}</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Chat Render Container
                    chat_box = st.container(height=420)

                    msgs = get_messages(current_user, target_chat)
                    
                    with chat_box:
                        st.markdown('<div class="chat-box">', unsafe_allow_html=True)
                        for m in msgs:
                            is_mine = (m["sender"] == current_user)
                            align = "sent" if is_mine else "received"
                            time_str = m.get("created_at", "")[11:16]

                            try:
                                dec_txt = cipher.decrypt(m['content'].encode()).decode()
                            except:
                                dec_txt = "⚠️ Encrypted Message"

                            file_bytes, file_name, file_mime = None, None, None
                            if "[FILE:" in dec_txt:
                                parts = dec_txt.split("[FILE:")
                                dec_txt = parts[0].strip()
                                meta_str, b64_str = parts[1].split("]", 1)
                                file_name, file_mime = meta_str.split(":", 1)
                                file_bytes = base64.b64decode(b64_str)

                            # HTML Bubble Render
                            bubble_html = f'<div class="msg-container {align}"><div class="bubble">'
                            if m.get("reply"):
                                bubble_html += f'<div class="reply-badge">↩️ {m["reply"]}</div>'
                            if dec_txt:
                                bubble_html += f'<div>{dec_txt}</div>'
                            bubble_html += f'<span class="msg-meta">{time_str}</span></div></div>'

                            st.markdown(bubble_html, unsafe_allow_html=True)

                            # Render Image/File
                            if file_bytes:
                                if file_mime and "image" in file_mime:
                                    st.image(file_bytes, caption=file_name, use_container_width=True)
                                else:
                                    st.download_button(f"⬇️ {file_name}", file_bytes, file_name=file_name, mime=file_mime, key=f"dl_{m['id']}")

                        st.markdown('</div>', unsafe_allow_html=True)

                    # Send Input Box
                    with st.form("send_msg_form", clear_on_submit=True):
                        in_msg = st.text_input("Message", placeholder="Type a message...", label_visibility="collapsed")
                        c_up, c_btn = st.columns([3, 1])
                        with c_up:
                            up_file = st.file_uploader("Attachment", type=["png", "jpg", "jpeg", "pdf"], label_visibility="collapsed")
                        with c_btn:
                            btn_send = st.form_submit_button("SEND 🚀", use_container_width=True)

                        if btn_send:
                            if not in_msg.strip() and not up_file:
                                st.warning("Empty message.")
                            else:
                                payload = in_msg.strip()
                                if up_file:
                                    f_b64 = base64.b64encode(up_file.read()).decode('utf-8')
                                    file_meta = f"[FILE:{up_file.name}:{up_file.type}]{f_b64}"
                                    payload = f"{payload}\n{file_meta}" if payload else file_meta

                                enc_payload = cipher.encrypt(payload.encode()).decode()
                                send_message(secrets.token_hex(8), current_user, target_chat, enc_payload)
                                st.rerun()
