import os
import io
import PIL.Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai  # <--- INI SUDAH DIGANTI (FIXED)
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- KONFIGURASI SDK BARU ---
client_ai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
client_db = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client_db.ai_k1_db

# --- DATABASE LOGIC ---
async def get_history(user_id: str):
    try:
        doc = await db.history.find_one({"user_id": user_id})
        return doc["messages"] if doc and "messages" in doc else []
    except:
        return []

async def save_history(user_id: str, messages: list):
    try:
        await db.history.update_one(
            {"user_id": user_id},
            {"$set": {"messages": messages}},
            upsert=True
        )
    except:
        pass

# --- UI FRONTEND ---
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
        <style>
            :root { --bg: #0d0d0d; --input: #212121; --accent: #10a37f; }
            body { background: var(--bg); color: #ececf1; font-family: sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; }
            #chat-box { flex: 1; overflow-y: auto; padding: 20px 10%; display: flex; flex-direction: column; gap: 15px; }
            .msg { max-width: 85%; padding: 12px; border-radius: 12px; line-height: 1.5; }
            .u { align-self: flex-end; background: var(--input); }
            .a { align-self: flex-start; border-left: 2px solid var(--accent); padding-left: 15px; }
            pre { background: #000; padding: 10px; border-radius: 5px; overflow-x: auto; }
            .input-area { padding: 20px 10%; background: var(--bg); border-top: 1px solid #333; }
            .box { background: var(--input); border-radius: 15px; display: flex; padding: 10px; align-items: center; border: 1px solid #444; }
            textarea { flex: 1; background: transparent; border: none; color: white; padding: 10px; outline: none; resize: none; font-size: 1rem; }
            button { background: var(--accent); color: white; border: none; padding: 10px 20px; border-radius: 10px; cursor: pointer; }
            #preview { max-width: 100px; display: none; margin-bottom: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div id="chat-box"></div>
        <div class="input-area">
            <img id="preview">
            <div class="box">
                <input type="file" id="fIn" hidden accept="image/*">
                <button onclick="document.getElementById('fIn').click()" style="background:#444; margin-right:5px;">📎</button>
                <textarea id="uIn" placeholder="Halo K1, bantu saya koding..." rows="1"></textarea>
                <button id="sBtn">Kirim</button>
            </div>
        </div>
        <script>
            const chatBox = document.getElementById('chat-box');
            const uIn = document.getElementById('uIn');
            const fIn = document.getElementById('fIn');
            const preview = document.getElementById('preview');

            fIn.onchange = () => {
                const [file] = fIn.files;
                if(file) { preview.src = URL.createObjectURL(file); preview.style.display = 'block'; }
            };

            function addMsg(txt, role) {
                const d = document.createElement('div');
                d.className = `msg ${role}`;
                d.innerHTML = role === 'a' ? marked.parse(txt) : txt;
                chatBox.appendChild(d);
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            async function send() {
                const text = uIn.value;
                const file = fIn.files[0];
                if(!text && !file) return;

                addMsg(text || "[Gambar]", 'u');
                uIn.value = ''; preview.style.display = 'none';

                const fd = new FormData();
                fd.append('user_id', 'user_k1');
                fd.append('message', text || "Apa isi gambar ini?");
                if(file) fd.append('file', file);

                try {
                    const res = await fetch('/chat', { method: 'POST', body: fd });
                    const data = await res.json();
                    addMsg(data.reply, 'a');
                } catch(e) { addMsg("Error: Server tidak merespon.", 'a'); }
                fIn.value = '';
            }

            document.getElementById('sBtn').onclick = send;
            uIn.onkeydown = (e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };
        </script>
    </body>
    </html>
    """

# --- API ENDPOINT (SDK BARU - FIXED) ---
@app.post("/chat")
async def chat_endpoint(user_id: str = Form(...), message: str = Form(...), file: UploadFile = File(None)):
    try:
        contents = []
        
        if file:
            img_bytes = await file.read()
            # Gunakan PIL untuk membaca gambar agar kompatibel dengan SDK baru
            img = PIL.Image.open(io.BytesIO(img_bytes))
            contents.append(img)
            
        contents.append(message)

        # Memanggil model dengan cara SDK google-genai yang benar
        response = client_ai.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config={
                "system_instruction": "Kamu AI K1, asisten ahli koding FiveM, web dev, dan fitness. Jawab dengan cerdas dan to the point."
            }
        )
        
        return {"reply": response.text}
    except Exception as e:
        # Menampilkan error di layar chat jika terjadi kegagalan API
        return {"reply": f"Maaf, AI K1 sedang kendala teknis: {str(e)}"}