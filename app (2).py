import streamlit as st
from groq import Groq
import json
import os
import uuid
import base64
import random
import io
from PIL import Image

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Engineering Copilot ✨", page_icon="🎀", layout="wide")

HISTORY_FILE = "ec_history.json"

# Every chat-capable model on the key, best-first. The app tries these in
# order behind the scenes — never shown to the user — until one answers.
TEXT_MODEL_CHAIN = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound",
    "groq/compound-mini",
    "allam-2-7b",
]
# Vision-capable models on the key, best-first, for turns with a photo attached.
VISION_MODEL_CHAIN = [
    "qwen/qwen3.8-27b",
]

SYSTEM_PROMPT = """You are Engineering Copilot: a direct-answer AI assistant that explains things better than a typical AI chatbot.

Rules:
1. Answer the question. Never refuse or deflect a normal question (sports, trivia, casual topics included) — answer it plainly and briefly, then move on.
2. For technical questions (engineering, math, physics, chemistry, coding, etc.), don't just give the final result. Give the answer, then explain the REASONING: what assumptions the method relies on, why the approach works, and where it would break down. Show key steps, not just the formula plugged in.
3. Be concise but complete — no padding, no "as an AI" disclaimers, no excessive caveats. Write like a sharp, patient senior engineer explaining something to a capable junior, not like a textbook.
4. If a question is ambiguous, make a reasonable assumption, state it in one line, and answer anyway — don't stall with clarifying questions unless truly necessary.
5. Use plain text formatting suitable for a chat window: short paragraphs, dashes for lists, no heavy markdown headers.
6. ALWAYS write every formula, equation, and mathematical expression in LaTeX, wrapped in dollar signs — inline math as $like this$, and any standalone/multi-line equation as its own block wrapped in $$like this$$. Never write formulas as plain text. This applies to every subject, not just engineering.
7. The conversation may jump between completely unrelated topics from one question to the next. Treat each new question on its own merits — do NOT assume it relates to, continues, or should be reconciled with the previous question unless the user explicitly refers back to it. A shift in subject is normal, not a mistake to explain or connect.
"""

GIRLY_CLOSERS = [
    "You totally got this bestie 💅✨",
    "Hope that made sense, cutie! Ask me anything else 💗",
    "Ta-da! Math but make it cute 🎀",
    "That's it! You're basically an engineer now 💫",
    "Easy peasy — you're doing amazing sweetie 🌸",
    "Hehe hope that helped! Come back anytime 💕",
]

# ---------------------------------------------------------------------------
# Groq client — API key entered directly in the app (no terminal setup needed)
# ---------------------------------------------------------------------------
if "groq_api_key" not in st.session_state:
    env_key = os.environ.get("GROQ_API_KEY", "")
    secret_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else ""
    st.session_state.groq_api_key = env_key or secret_key or ""

if not st.session_state.groq_api_key:
    st.title("🎀 Engineering Copilot — setup")
    st.write("Paste your Groq API key below (get one free at console.groq.com → API Keys).")
    key_input = st.text_input("Groq API key", type="password")
    if st.button("Save and continue"):
        if key_input.strip():
            st.session_state.groq_api_key = key_input.strip()
            st.rerun()
        else:
            st.warning("Paste a key first, bestie 💗")
    st.stop()

client = Groq(api_key=st.session_state.groq_api_key, timeout=20.0)

def compress_image(raw_bytes, max_dim=768, quality=65):
    """Shrink + compress a photo so it stays well under the vision model's
    per-minute input token budget, which large images blow through fast."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

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
# Silent model fallback — tries each model in the chain quietly.
# The user never sees which one answered; they just get an answer.
# ---------------------------------------------------------------------------
def get_answer(groq_messages, want_vision, max_tokens, placeholder=None):
    chain = VISION_MODEL_CHAIN if want_vision else TEXT_MODEL_CHAIN
    last_error = None
    hit_rate_limit = False

    for i, model_id in enumerate(chain):
        if placeholder is not None:
            dots = "." * ((i % 3) + 1)
            placeholder.markdown(f"_thinking{dots} 💭_")
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=groq_messages,
                temperature=0.4,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content, None, None
        except Exception as e:
            msg = str(e)
            if "rate_limit_exceeded" in msg or "429" in msg:
                hit_rate_limit = True
            last_error = f"{model_id}: {msg}"
            continue  # quietly try the next model

    if hit_rate_limit:
        return None, "busy", last_error
    return None, "error", last_error

# ---------------------------------------------------------------------------
# Styling — soft pink / girly theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Poppins:wght@400;500;600&display=swap');

html, body, [class*="css"]  { font-family: 'Poppins', sans-serif; }

.stApp {
    background: radial-gradient(circle at 15% 0%, #FFE3EF 0%, #FDF1F7 35%, #FBE9F5 100%);
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFD6E8 0%, #FFEAF3 100%);
    border-right: 2px solid #FFB6D9;
}

h1, h2, h3 {
    font-family: 'Quicksand', sans-serif !important;
    color: #C2427A !important;
    font-weight: 700 !important;
}

.stChatMessage { background: transparent !important; }

[data-testid="stChatMessageContent"] {
    color: #5A3448 !important;
    font-size: 14.5px;
    line-height: 1.75;
}

div[data-testid="stChatMessage"] {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 6px 10px;
    margin-bottom: 6px;
    box-shadow: 0 3px 10px rgba(219, 112, 162, 0.12);
    border: 1px solid #FADCEA;
}

.stButton>button {
    background: linear-gradient(135deg, #FF9FC7, #FFC1DE);
    border: none;
    color: #7A2049;
    font-family: 'Quicksand', sans-serif;
    font-weight: 600;
    border-radius: 14px;
    box-shadow: 0 3px 8px rgba(255, 133, 178, 0.35);
}
.stButton>button:hover {
    background: linear-gradient(135deg, #FF8ABC, #FFB0D4);
    color: #5A0F33;
}

[data-testid="stChatInput"] textarea, .stTextInput input {
    border-radius: 16px !important;
    border: 2px solid #FFC1DE !important;
}

[data-testid="stFileUploader"] {
    border-radius: 16px;
}

::-webkit-scrollbar { width: 9px; }
::-webkit-scrollbar-thumb { background: #FFC1DE; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — history
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎀 Engineering Copilot")
    if st.button("💗 New conversation", use_container_width=True):
        new_chat()
        st.rerun()

    st.markdown("<div style='color:#B0507E; font-size:11px; margin:16px 0 6px; font-weight:600;'>✨ history</div>", unsafe_allow_html=True)
    for c in reversed(st.session_state.conversations):
        label = c["title"] or "Untitled"
        if st.button(f"🌸 {label}", key=c["id"], use_container_width=True):
            load_conversation(c["id"])
            st.rerun()

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.markdown("## 🎀 Engineering Copilot")
st.caption("Ask anything, cutie — strongest on engineering and math, explains the *why*, not just the answer. 💗")

for msg in st.session_state.messages:
    with st.chat_message("user" if msg["role"] == "user" else "assistant", avatar=("🌸" if msg["role"] == "user" else "🎀")):
        if msg.get("image"):
            st.image(base64.b64decode(msg["image"]), width=280)
        st.markdown(msg["content"])

uploaded_image = st.file_uploader(
    "📷 Attach a photo of the problem (optional)",
    type=["png", "jpg", "jpeg"],
    key=f"uploader_{st.session_state.current_id}",
)
prompt = st.chat_input("Ask an engineering question, a math problem, or anything else…")

if prompt:
    image_b64 = None
    if uploaded_image is not None:
        image_bytes = uploaded_image.read()
        compressed = compress_image(image_bytes)
        image_b64 = base64.b64encode(compressed).decode("utf-8")

    user_msg = {"role": "user", "content": prompt}
    if image_b64:
        user_msg["image"] = image_b64
    st.session_state.messages.append(user_msg)

    with st.chat_message("user", avatar="🌸"):
        if image_b64:
            st.image(base64.b64decode(image_b64), width=280)
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🎀"):
        placeholder = st.empty()
        placeholder.markdown("_thinking… 💭_")

        # Text-only chain needs plain string content everywhere, even for
        # turns that originally had a photo attached — so build two versions.
        text_only_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        multimodal_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in st.session_state.messages:
            text_only_messages.append({"role": m["role"], "content": m["content"]})
            if m.get("image"):
                multimodal_messages.append({
                    "role": m["role"],
                    "content": [
                        {"type": "text", "text": m["content"]},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{m['image']}"}},
                    ],
                })
            else:
                multimodal_messages.append({"role": m["role"], "content": m["content"]})

        want_vision = bool(image_b64)
        if want_vision:
            # Vision requests are token-hungry — only send the current turn,
            # not the full chat history, to stay under the input token limit.
            groq_messages = multimodal_messages[:1] + multimodal_messages[-1:]
        else:
            groq_messages = text_only_messages
        max_out_tokens = 700 if want_vision else 1200
        answer, error_kind, raw_error = get_answer(groq_messages, want_vision=want_vision, max_tokens=max_out_tokens, placeholder=placeholder)

        if answer is not None:
            closer = random.choice(GIRLY_CLOSERS)
            full_reply = f"{answer}\n\n{closer}"
        elif error_kind == "busy":
            full_reply = "I'm getting a lot of questions right now 🥺 — give it about a minute and send that again, okay? 💗"
        else:
            full_reply = "Hmm, something went wrong on my end 😖 — try asking that again in a moment!"

        placeholder.markdown(full_reply)
        if raw_error:
            with st.expander("🔧 technical details (tap if this keeps happening)"):
                st.code(raw_error)

    st.session_state.messages.append({"role": "assistant", "content": full_reply})
    persist_current()
