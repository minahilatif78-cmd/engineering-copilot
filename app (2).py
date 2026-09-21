import streamlit as st
from groq import Groq
import json
import os
import time
import uuid

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Engineering Copilot", page_icon="📐", layout="wide")

CANDIDATE_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
]
HISTORY_FILE = "ec_history.json"

SYSTEM_PROMPT = """You are Engineering Copilot: a direct-answer AI assistant that explains things better than a typical AI chatbot.

Rules:
1. Answer the question. Never refuse or deflect a normal question (sports, trivia, casual topics included) — answer it plainly and briefly, then move on.
2. For technical questions (engineering, math, physics, chemistry, coding, etc.), don't just give the final result. Give the answer, then explain the REASONING: what assumptions the method relies on, why the approach works, and where it would break down. Show key steps, not just the formula plugged in.
3. Be concise but complete — no padding, no "as an AI" disclaimers, no excessive caveats. Write like a sharp, patient senior engineer explaining something to a capable junior, not like a textbook.
4. If a question is ambiguous, make a reasonable assumption, state it in one line, and answer anyway — don't stall with clarifying questions unless truly necessary.
5. Use plain text formatting suitable for a chat window: short paragraphs, dashes for lists, no heavy markdown headers.
"""

# ---------------------------------------------------------------------------
# Groq client — API key entered directly in the app (no terminal setup needed)
# ---------------------------------------------------------------------------
if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = os.environ.get("GROQ_API_KEY", "")

if not st.session_state.groq_api_key:
    st.title("📐 Engineering Copilot — setup")
    st.write("Paste your Groq API key below (get one free at console.groq.com → API Keys).")
    key_input = st.text_input("Groq API key", type="password")
    if st.button("Save and continue"):
        if key_input.strip():
            st.session_state.groq_api_key = key_input.strip()
            st.rerun()
        else:
            st.warning("Paste a key first.")
    st.stop()

client = Groq(api_key=st.session_state.groq_api_key)

# ---------------------------------------------------------------------------
# Persistent history (simple JSON file — swap for a DB later if you want)
# ---------------------------------------------------------------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

if "conversations" not in st.session_state:
    st.session_state.conversations = load_history()
if "current_id" not in st.session_state:
    st.session_state.current_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

def new_chat():
    st.session_state.current_id = None
    st.session_state.messages = []

def load_conversation(conv_id):
    for c in st.session_state.conversations:
        if c["id"] == conv_id:
            st.session_state.current_id = conv_id
            st.session_state.messages = c["messages"]
            return

def persist_current():
    if not st.session_state.messages:
        return
    if st.session_state.current_id is None:
        st.session_state.current_id = str(uuid.uuid4())
        title = st.session_state.messages[0]["content"][:42]
        st.session_state.conversations.append(
            {"id": st.session_state.current_id, "title": title, "messages": st.session_state.messages}
        )
    else:
        for c in st.session_state.conversations:
            if c["id"] == st.session_state.current_id:
                c["messages"] = st.session_state.messages
    save_history(st.session_state.conversations)

# ---------------------------------------------------------------------------
# Styling — blueprint / drafting-table theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"]  { font-family: 'IBM Plex Mono', monospace; }

.stApp {
    background-color: #0F1B2D;
    background-image:
        linear-gradient(rgba(157,197,224,0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(157,197,224,0.06) 1px, transparent 1px);
    background-size: 28px 28px;
}

section[data-testid="stSidebar"] {
    background-color: rgba(10,18,32,0.6);
    border-right: 1px solid rgba(157,197,224,0.16);
}

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; color: #E7EEF5 !important; }

.stChatMessage { background: transparent !important; }

[data-testid="stChatMessageContent"] {
    color: #E7EEF5 !important;
    font-size: 14px;
    line-height: 1.7;
}

.stButton>button {
    background-color: transparent;
    border: 1px solid #8A5E36;
    color: #CD8A4E;
    font-family: 'IBM Plex Mono', monospace;
    border-radius: 4px;
}
.stButton>button:hover {
    border-color: #CD8A4E;
    background-color: rgba(205,138,78,0.08);
    color: #DE9A5F;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — history
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📐 Engineering Copilot")
    if st.button("+ New conversation", use_container_width=True):
        new_chat()
        st.rerun()

    MODEL = st.selectbox("Model", CANDIDATE_MODELS, index=0)
    st.caption("If you get a 'model_not_found' error, just pick a different one from this list.")

    if st.button("Check my key's available models", use_container_width=True):
        try:
            real_models = [m.id for m in client.models.list().data]
            st.success("Your key can access:")
            st.code("\n".join(real_models))
        except Exception as e:
            st.error(f"Key check failed: {e}")

    st.markdown("<div style='color:#8CA0B8; font-size:11px; margin:14px 0 6px;'>history</div>", unsafe_allow_html=True)
    for c in reversed(st.session_state.conversations):
        label = c["title"] or "Untitled"
        if st.button(label, key=c["id"], use_container_width=True):
            load_conversation(c["id"])
            st.rerun()

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.markdown("## Engineering Copilot")
st.caption("Ask anything — strongest on engineering and math, explains the *why*, not just the answer.")

for msg in st.session_state.messages:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask an engineering question, a math problem, or anything else…")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("_thinking…_")

        groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]

        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=groq_messages,
                stream=True,
                temperature=0.4,
            )
            full_reply = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_reply += delta
                placeholder.markdown(full_reply + "▌")
            placeholder.markdown(full_reply)
        except Exception as e:
            full_reply = f"Could not get a response: {e}"
            placeholder.markdown(full_reply)

    st.session_state.messages.append({"role": "assistant", "content": full_reply})
    persist_current()
