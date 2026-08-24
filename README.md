# CYBER SECURE MESSENGER

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Encryption](https://img.shields.io/badge/Encryption-AES--256-blue?style=for-the-badge)

A high-performance, real-time private messaging application featuring End-to-End Encryption (E2EE). Built using pure Vibe Coding principles, it delivers a modern UI inspired by Instagram Direct and Facebook Messenger, powered by Supabase (PostgreSQL Cloud DB) for permanent cloud persistence and multi-device support.

---

## Overview

Cyber Secure Messenger is engineered to combine absolute privacy with modern messaging convenience. Developed through pure vibe coding, the platform provides end-to-end encryption for text and file transfers, robust cloud persistence via Supabase, responsive chat interface layouts, session recovery across browser reloads, comprehensive friend management tools, and strong account recovery protocols.

---

## Key Features

1. Vibe Coded Architecture: Developed and continuously optimized using AI-driven vibe coding methods for ultra-fast iteration and smooth interface styling.
2. End-to-End Encryption: Client-side Fernet symmetric encryption safeguards all messages and uploaded media prior to cloud storage.
3. Cloud Database Persistence: Fully integrated with Supabase PostgreSQL database to ensure accounts, user relationships, and chat histories remain permanently saved across server restarts.
4. Responsive UI and UX: Seamlessly adapts to desktop computers and mobile browsers with Instagram and Messenger inspired chat bubbles.
5. Session Persistence: Keeps users authenticated during page refreshes using URL parameter state tracking.
6. Media and File Attachments: Inline image rendering with expandable previews alongside direct download capabilities for documents such as PDFs and TXT files.
7. Friend Management System: Search for contacts using unique permanent User IDs (#XXXX), process pending friend requests, configure nicknames, and customize user statuses or bios.
8. Privacy and Account Recovery: Built-in user blocking mechanisms, password management, and hashed recovery key functionality for account restoration.

---

## Tech Stack

- Methodology: Vibe Coding
- Frontend / UI: Streamlit, Custom Responsive CSS
- Backend and Database: Supabase (PostgreSQL Cloud Database)
- Security and Cryptography: Python cryptography (Fernet/AES-256 equivalent), SHA-256 Hashing

---

## Local Installation and Setup

1. Clone the repository:
   git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git
   cd YOUR_REPOSITORY_NAME

2. Install required dependencies:
   pip install -r requirements.txt

3. Configure Secrets:
   Create a .streamlit folder in the root directory, then create a secrets.toml file inside it with your credentials:
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-supabase-publishable-key"

4. Launch the application:
   streamlit run main.py

---

## Author

Vibe Coded by Mohammad Janaideh.
