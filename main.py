import os
import io
import PIL.Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

# Middleware agar lancar jaya
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CONFIG API & DATABASE ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# Pastikan MONGO_URI sudah benar di Variables Railway
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.ai_k1_db

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Kamu AI K1, asisten ahli koding FiveM, web dev, dan fitness. Berikan jawaban cerdas, singkat, dan gunakan format Markdown untuk kode."
)

# --- FIXED DATABASE LOGIC ---
async def get_history(user_id: str):
    try:
        # Menghindari error sinkronisasi di Python 3.13
        doc = await db.history.find_one({"user_id": user_id})
        return doc["messages"] if doc and "messages" in doc else []
    except Exception as e:
        print(f"DB Read Error: {e}")
        return []

async def save_history(user_id: str, messages: list):
    try:
        await db.history.update_one(
            {"user_id": user_id},
            {"$set": {"messages": messages}},
            upsert=True
        )
    except Exception as e:
        print(f"DB Save Error: {e}")

# --- UI FRONTEND (ChatGPT Style) ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI K1 Workspace</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <style>
            :root { --bg: #0d0d0d; --input: #212121; --accent: #10a37f; }
            body { background: var(--bg); color: #ececf1; font-family: sans-serif; margin: 0; display: flex; height: 100vh; flex-direction: column; }
            #chat-box { flex: 1; overflow-y: auto; padding: 20px 15%; display: flex; flex-direction: column; gap: 20px; }
            .row { display: flex; flex-direction: column; }
            .user { align-items: flex-end; }
            .ai { align-items: flex-start; }
            .bubble { max-width: 80%; padding: 12px 18px; border-radius: 15px; line-height: 1.6; }
            .user-bubble { background: var(--input); }
            pre { background: #000; padding: 15px; border-radius: 8px; overflow-x: auto; width: 100%; box-sizing: border-box; }
            .input-area { padding: 20px 15%; background: var(--bg); }
            .box { background: var(--input); border-radius: 12px; display: flex; padding: 10px; align-items: flex-end; border: 1px solid #444; }
            textarea { flex: 1; background: transparent; border: none; color: white; padding: 10px; outline: none; resize: none; font-size: 1rem; }
            button { background: var(--accent); color: white; border: none; padding: 10px 15px; border-radius: 8px; cursor: pointer; }
            #preview { max-width: 150px; display: none; margin-bottom: 10px; border-radius: 8px; border: 1px solid var(--accent); }
        </style>
    </head>
    <body>
        <div id="chat-box"></div>
        <div class="input-area">
            <img id="preview">
            <div class="box">
                <label style="cursor:pointer; padding: 10px;">
                    <input type="file" id="fIn" hidden accept="image/*"> 📎
                </label>
                <textarea id="uIn" placeholder="Kirim pesan atau gambar..." rows="1"></textarea>
                <button id="sBtn">➤</button>
            </div>
        </div>
        <script>
            const chat = document.getElementById('chat-box');
            const uIn = document.getElementById('uIn');
            const fIn = document.getElementById('fIn');
            const prev = document.getElementById('preview');

            fIn.onchange = () => {
                const [file] = fIn.files;
                if(file) { prev.src = URL.createObjectURL(file); prev.style.display = 'block'; }
            };

            function add(text, role) {
                const row = document.createElement('div');
                row.className = `row ${role}`;
                const b = document.createElement('div');
                b.className = `bubble ${role}-bubble`;
                if(role === 'ai') {
                    b.innerHTML = marked.parse(text);
                    b.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
                } else { b.innerText = text; }
                row.appendChild(b);
                chat.appendChild(row);
                chat.scrollTop = chat.scrollHeight;
            }

            async function send() {
                const txt = uIn.value;
                const file = fIn.files[0];
                if(!txt && !file) return;

                add(txt || "Mengirim gambar...", 'user');
                uIn.value = ''; uIn.style.height = 'auto'; prev.style.display = 'none';

                const fd = new FormData();
                fd.append('user_id', 'user_k1');
                fd.append('message', txt || "Apa isi gambar ini?");
                if(file) fd.append('file', file);

                try {
                    const res = await fetch('/chat', { method: 'POST', body: fd });
                    const data = await res.json();
                    add(data.reply, 'ai');
                } catch(e) { add("Error: Gagal terhubung.", 'ai'); }
                fIn.value = '';
            }

            document.getElementById('sBtn').onclick = send;
            uIn.onkeydown = (e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };
        </script>
    </body>
    </html>
    """

# --- FIXED API ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(user_id: str = Form(...), message: str = Form(...), file: UploadFile = File(None)):
    try:
        # Ambil history secara asinkron
        history = await get_history(user_id)
        chat_session = model.start_chat(history=history[-10:]) # Batasi 10 pesan terakhir

        if file:
            content = await file.read()
            img = PIL.Image.open(io.BytesIO(content))
            response = chat_session.send_message([message, img])
        else:
            response = chat_session.send_message(message)
        
        # Simpan history baru
        await save_history(user_id, chat_session.history)
        
        return {"reply": response.text}
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"reply": f"Maaf, AI K1 sedang kendala teknis. Error: {str(e)}"}