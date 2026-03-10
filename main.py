import os
import io
import PIL.Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CONFIG ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.ai_k1_db

# Menggunakan model Flash agar analisis gambar sangat cepat
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Kamu AI K1, asisten serba bisa. Gunakan Markdown untuk kodingan. Jika user kirim gambar, analisis dengan detail."
)

async def get_history(user_id):
    doc = await db.history.find_one({"user_id": user_id})
    return doc["messages"] if doc else []

async def save_history(user_id, messages):
    await db.history.update_one({"user_id": user_id}, {"$set": {"messages": messages}}, upsert=True)

# --- UI FRONTEND ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI K1 - Workspace</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <style>
            :root { --sidebar: #000; --main: #0d0d0d; --input: #212121; --accent: #10a37f; }
            body { background: var(--main); color: #ececf1; font-family: 'Sentry', sans-serif; margin: 0; display: flex; height: 100vh; }
            
            #chat-container { flex: 1; display: flex; flex-direction: column; position: relative; }
            #messages { flex: 1; overflow-y: auto; padding: 20px 10%; scroll-behavior: smooth; }
            
            .row { margin-bottom: 30px; display: flex; flex-direction: column; }
            .user-row { align-items: flex-end; }
            .ai-row { align-items: flex-start; }
            
            .bubble { max-width: 85%; padding: 10px 20px; border-radius: 15px; line-height: 1.6; }
            .user-bubble { background: var(--input); color: #fff; }
            .ai-bubble { background: transparent; color: #ececf1; }
            
            pre { background: #000 !important; padding: 15px; border-radius: 8px; overflow-x: auto; border: 1px solid #333; }
            code { font-family: 'Fira Code', monospace; font-size: 0.9rem; }

            .input-box { padding: 20px 10%; background: var(--main); }
            .input-wrapper { background: var(--input); border-radius: 15px; display: flex; align-items: flex-end; padding: 10px; border: 1px solid #444; }
            
            textarea { flex: 1; background: transparent; border: none; color: white; padding: 10px; outline: none; resize: none; max-height: 200px; font-size: 1rem; }
            button { background: var(--accent); color: white; border: none; padding: 8px 15px; border-radius: 8px; cursor: pointer; font-weight: bold; margin-left: 10px; }
            .upload-label { cursor: pointer; padding: 10px; color: #aaa; }
            .preview-img { max-width: 200px; border-radius: 10px; margin-bottom: 10px; display: none; border: 1px solid var(--accent); }
        </style>
    </head>
    <body>
        <div id="chat-container">
            <div id="messages"></div>
            
            <div class="input-box">
                <img id="imgPreview" class="preview-img">
                <div class="input-wrapper">
                    <label class="upload-label">
                        <input type="file" id="fileInput" hidden accept="image/*"> 📎
                    </label>
                    <textarea id="userInput" placeholder="Tanya sesuatu ke AI K1..." rows="1"></textarea>
                    <button id="sendBtn">➤</button>
                </div>
            </div>
        </div>

        <script>
            const msgDiv = document.getElementById('messages');
            const input = document.getElementById('userInput');
            const fileInput = document.getElementById('fileInput');
            const imgPreview = document.getElementById('imgPreview');

            // Handle Preview Gambar
            fileInput.onchange = () => {
                const [file] = fileInput.files;
                if (file) {
                    imgPreview.src = URL.createObjectURL(file);
                    imgPreview.style.display = 'block';
                }
            };

            // Auto-resize textarea
            input.oninput = () => {
                input.style.height = 'auto';
                input.style.height = input.scrollHeight + 'px';
            };

            function addMessage(content, role) {
                const row = document.createElement('div');
                row.className = `row ${role}-row`;
                const bubble = document.createElement('div');
                bubble.className = `bubble ${role}-bubble`;
                
                if(role === 'ai') {
                    bubble.innerHTML = marked.parse(content);
                    bubble.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
                } else {
                    bubble.innerText = content;
                }
                
                row.appendChild(bubble);
                msgDiv.appendChild(row);
                msgDiv.scrollTop = msgDiv.scrollHeight;
            }

            async function sendMessage() {
                const text = input.value;
                const file = fileInput.files[0];
                if (!text && !file) return;

                addMessage(text || "Menganalisis file...", 'user');
                input.value = '';
                input.style.height = 'auto';
                imgPreview.style.display = 'none';

                const fd = new FormData();
                fd.append('user_id', 'k1_main_user');
                fd.append('message', text || "Jelaskan gambar ini.");
                if (file) fd.append('file', file);

                try {
                    const res = await fetch('/chat', { method: 'POST', body: fd });
                    const data = await res.json();
                    addMessage(data.reply, 'ai');
                } catch (e) {
                    addMessage("Koneksi terputus.", 'ai');
                }
                fileInput.value = '';
            }

            document.getElementById('sendBtn').onclick = sendMessage;
            input.onkeydown = (e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } };
        </script>
    </body>
    </html>
    """

@app.post("/chat")
async def chat_endpoint(user_id: str = Form(...), message: str = Form(...), file: UploadFile = File(None)):
    history = await get_history(user_id)
    chat = model.start_chat(history=history[-12:]) # Memori 12 pesan terakhir
    
    try:
        if file:
            img = PIL.Image.open(io.BytesIO(await file.read()))
            response = chat.send_message([message, img])
        else:
            response = chat.send_message(message)
        
        await save_history(user_id, chat.history)
        return {"reply": response.text}
    except Exception as e:
        return {"reply": f"Terjadi kesalahan teknis: {str(e)}"}