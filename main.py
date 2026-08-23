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
                    st.session_state.current_user = u_in
                    st.session_state.current_page = "Dashboard"
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

            if st.button("CREATE ACCOUNT", use_container_width=True):
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
                    assigned_role = "admin" if len(data["users"]) == 0 else "user"

                    data["users"][r_u] = {
                        "password": hash_data(r_p),
                        "recovery_key": hash_data(rec_k),
                        "role": assigned_role,
                        "blocked": []
                    }
                    save_data(data)
                    log_audit("REGISTER_SUCCESS", f"User '{r_u}' registered.")

                    st.success("Account created successfully!")
                    st.markdown(f"""
                    <div class="recovery-info">
                        <strong>SAVE RECOVERY KEY:</strong><br>
                        <code>{rec_k}</code>
                    </div>
                    """, unsafe_allow_html=True)

        with tab_rec:
            st.markdown("##### Reset Password")
            f_u = st.text_input("Username", key="f_u")
            f_k = st.text_input("Recovery Key", key="f_k")
            f_p = st.text_input("New Password", type="password", key="f_p")
            f_c = st.text_input("Confirm New Password", type="password", key="f_c")

            if st.button("RESET PASSWORD", use_container_width=True):
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

    st.sidebar.markdown(f"### 👤 {current_user}")
    st.sidebar.markdown(f"Role: `{role.upper()}`")
    st.sidebar.markdown("---")

    if st.sidebar.button("🏠 Dashboard", use_container_width=True):
        st.session_state.current_page = "Dashboard"
        st.rerun()

    menu_opts = ["💬 Messages", "🚫 Blocklist", "⚙️ Settings"]
    if role == "admin":
        menu_opts.append("📊 Admin Panel")

    sel_page = st.sidebar.radio("NAVIGATION", menu_opts, key="nav_sel")
    if sel_page != st.session_state.current_page and sel_page != "Dashboard":
        st.session_state.current_page = sel_page

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.current_page = "Dashboard"
        st.rerun()

    if st.session_state.current_page == "Dashboard":
        st.markdown("### 📊 System Overview")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown(f"""
            <div class="card-box">
                <h3 style="color:#e5e7eb; margin:0;">{len(data['users'])}</h3>
                <small style="color:#9ca3af;">Registered Users</small>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div class="card-box">
                <h3 style="color:#e5e7eb; margin:0;">{len(data['messages'])}</h3>
                <small style="color:#9ca3af;">Total Transmissions</small>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            my_count = sum(1 for m in data['messages'] if m.get('to') == current_user or m.get('from') == current_user)
            st.markdown(f"""
            <div class="card-box">
                <h3 style="color:#e5e7eb; margin:0;">{my_count}</h3>
                <small style="color:#9ca3af;">Your Conversations</small>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💬 Open Messages", use_container_width=True):
            st.session_state.current_page = "💬 Messages"
            st.rerun()

    elif st.session_state.current_page == "💬 Messages":
        other_users = [u for u in data["users"] if u != current_user]

        if not other_users:
            st.info("No other registered accounts available.")
        else:
            col_contacts, col_chat = st.columns([1, 2.2])

            with col_contacts:
                st.markdown("##### Users")
                for u in other_users:
                    is_sel = (st.session_state.selected_chat == u)
                    btn_txt = f"🟢 {u}" if is_sel else f"👤 {u}"
                    if st.button(btn_txt, key=f"user_sel_{u}", use_container_width=True):
                        st.session_state.selected_chat = u
                        st.rerun()

            with col_chat:
                target_chat = st.session_state.selected_chat
                if not target_chat:
                    st.info("Select a user from the left panel to display chat history.")
                else:
                    st.markdown(f"""
                    <div class="chat-header-bar">
                        <strong>Chatting with: {target_chat}</strong>
                        <small style="float:right; color:#9ca3af;">AES Encrypted</small>
                    </div>
                    """, unsafe_allow_html=True)

                    chat_container = st.container(height=420)

                    @st.fragment(run_every="2s")
                    def render_live_chat():
                        live_data = load_data()
                        msgs_to_burn = []
                        
                        with chat_container:
                            for m in live_data["messages"]:
                                f_user, t_user = m.get("from"), m.get("to")
                                if (f_user == current_user and t_user == target_chat) or (f_user == target_chat and t_user == current_user):
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
                                        txt_display = "[Decryption Error]"
                                        file_bytes = None

                                    burn_str = " 🔥" if m.get("burn") else ""
                                    time_str = m['time'].split(" ")[1][:5]
                                    is_mine = (f_user == current_user)

                                    bubble_class = "bubble-sent" if is_mine else "bubble-received"
                                    
                                    if txt_display:
                                        st.markdown(f"""
                                        <div class="{bubble_class}">
                                            {txt_display}{burn_str}
                                            <span class="bubble-time">{time_str}</span>
                                        </div>
                                        """, unsafe_allow_html=True)

                                    if file_bytes:
                                        with st.expander(f"📁 Attachment: {file_name}", expanded=True):
                                            if file_mime and "image" in file_mime:
                                                st.image(file_bytes, caption=file_name, use_container_width=True)
                                            elif file_mime and "text" in file_mime:
                                                try:
                                                    st.caption(file_bytes.decode('utf-8')[:200] + "...")
                                                except Exception:
                                                    pass

                                            st.download_button(
                                                label=f"⬇️ Download {file_name}",
                                                data=file_bytes,
                                                file_name=file_name,
                                                mime=file_mime,
                                                key=f"dl_{m['time']}_{f_user}"
                                            )

                                    if not is_mine and m.get("burn"):
                                        msgs_to_burn.append(m)

                            # كود JavaScript فعّال لسحب السكرول لأسفل الحاوية تلقائياً
                            components.html("""
                            <script>
                                var containers = window.parent.document.querySelectorAll('div[data-testid="stElementContainer"]');
                                containers.forEach(function(c) {
                                    var parentBox = c.closest('div[data-id]');
                                    if (parentBox) {
                                        parentBox.scrollTop = parentBox.scrollHeight;
                                    }
                                });
                                var chatBox = window.parent.document.querySelector('div[data-testid="stVerticalBlockBorderWrapper"]');
                                if (chatBox) {
                                    chatBox.scrollTop = chatBox.scrollHeight;
                                }
                            </script>
                            """, height=0)

                        if msgs_to_burn:
                            for bm in msgs_to_burn:
                                live_data["messages"].remove(bm)
                                log_audit("MESSAGE_BURNED", f"Burned msg from '{bm['from']}' to '{bm['to']}'.")
                            save_data(live_data)

                    render_live_chat()

                    st.markdown("<div style='clear:both;'></div><br>", unsafe_allow_html=True)

                    with st.form(key="send_form", clear_on_submit=True):
                        in_msg = st.text_input("Type a message...", key="in_msg_key", label_visibility="collapsed")
                        up_file = st.file_uploader("Attach File (Img, PDF, TXT)", type=["png", "jpg", "jpeg", "pdf", "txt"], label_visibility="collapsed")
                        
                        c_chk, c_btn = st.columns([1, 1])
                        with c_chk:
                            chk_burn = st.checkbox("Self-destruct")
                        with c_btn:
                            btn_sub = st.form_submit_button("SEND 🚀", use_container_width=True)

                        if btn_sub:
                            fresh_data = load_data()
                            recipient_blocked = fresh_data["users"][target_chat].get("blocked", [])
                            if current_user in recipient_blocked:
                                st.error("User has blocked you.")
                            elif not in_msg.strip() and not up_file:
                                st.warning("Cannot send an empty message or empty file.")
                            else:
                                final_payload = in_msg.strip()
                                
                                if up_file:
                                    f_bytes = up_file.read()
                                    b64_data = base64.b64encode(f_bytes).decode('utf-8')
                                    file_meta = f"[FILE:{up_file.name}:{up_file.type}]{b64_data}"
                                    final_payload = f"{final_payload}\n{file_meta}" if final_payload else file_meta

                                enc_content = cipher.encrypt(final_payload.encode()).decode()
                                fresh_data["messages"].append({
                                    "from": current_user,
                                    "to": target_chat,
                                    "content": enc_content,
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "burn": chk_burn
                                })
                                save_data(fresh_data)
                                log_audit("MESSAGE_SENT", f"From '{current_user}' to '{target_chat}' (with attachment).")
                                st.rerun()

    elif st.session_state.current_page == "🚫 Blocklist":
        st.markdown("### 🚫 Blocklist Management")
        block_list = data["users"][current_user].setdefault("blocked", [])
        st.write(f"Currently Blocked: `{', '.join(block_list) if block_list else 'None'}`")
        
        targets = [u for u in data["users"] if u != current_user]
        if targets:
            t_user = st.selectbox("Select Target User", targets)
            b_col1, b_col2 = st.columns(2)
            
            with b_col1:
                if st.button("BLOCK USER", use_container_width=True) and t_user not in block_list:
                    block_list.append(t_user)
                    save_data(data)
                    log_audit("USER_BLOCKED", f"'{current_user}' blocked '{t_user}'.")
                    st.success(f"Blocked {t_user}.")
                    st.rerun()
            
            with b_col2:
                if st.button("UNBLOCK USER", use_container_width=True) and t_user in block_list:
                    block_list.remove(t_user)
                    save_data(data)
                    log_audit("USER_UNBLOCKED", f"'{current_user}' unblocked '{t_user}'.")
                    st.success(f"Unblocked {t_user}.")
                    st.rerun()

    elif st.session_state.current_page == "⚙️ Settings":
        st.markdown("### ⚙️ Account Settings")
        st.write(f"User: **{current_user}**")
        
        curr_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        conf_pwd = st.text_input("Confirm Password", type="password")

        if st.button("UPDATE PASSWORD", use_container_width=True):
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
        st.markdown("##### User Registry")
        st.table([{"User": u, "Role": info.get("role"), "Blocked": len(info.get("blocked", []))} for u, info in data["users"].items()])
        
        st.markdown("##### System Audit Logs")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                st.code("".join(f.readlines()[-20:]))
        else:
            st.info("No audit logs found.")
```[cite: 6]
