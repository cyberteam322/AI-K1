import os
import io
import PIL.Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Izinkan akses dari mana saja
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- KONFIGURASI ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.ai_k1_db
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Nama kamu AI K1. Ahli koding FiveM & Fitness. Bicara singkat, keren, dan natural."
)

# --- DATABASE LOGIC ---
async def get_history(user_id):
    doc = await db.history.find_one({"user_id": user_id})
    return doc["messages"] if doc else []

async def save_history(user_id, messages):
    await db.history.update_one({"user_id": user_id}, {"$set": {"messages": messages}}, upsert=True)

# --- UI FRONTEND (Tampilan Terintegrasi) ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI K1 - NEURAL CORE</title>
        <link href="https://fonts.googleapis.com/css2?family=Orbitron&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            :root { --cyan: #00f2ff; --pink: #ff0055; --bg: #050505; }
            body { background: var(--bg); color: white; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; overflow: hidden; background: radial-gradient(circle at center, #111 0%, #000 100%); }
            .container { text-align: center; width: 90%; max-width: 450px; }
            h1 { font-family: 'Orbitron'; font-size: 0.9rem; letter-spacing: 5px; color: var(--cyan); margin-bottom: 50px; text-shadow: 0 0 15px var(--cyan); }
            
            /* Orb Animation */
            .orb-container { position: relative; width: 180px; height: 180px; margin: 0 auto 40px; cursor: pointer; }
            .orb { width: 100%; height: 100%; border-radius: 50%; background: rgba(0, 242, 255, 0.05); border: 2px solid rgba(0, 242, 255, 0.2); display: flex; align-items: center; justify-content: center; transition: 0.5s; }
            .orb-inner { width: 60px; height: 60px; background: var(--cyan); border-radius: 50%; box-shadow: 0 0 40px var(--cyan); transition: 0.3s; }
            
            .listening .orb { border-color: var(--pink); box-shadow: 0 0 40px rgba(255, 0, 85, 0.3); }
            .listening .orb-inner { background: var(--pink); box-shadow: 0 0 50px var(--pink); transform: scale(1.3); animation: pulse 1s infinite; }
            
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            
            .glass { background: rgba(255,255,255,0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.08); padding: 25px; border-radius: 25px; margin-top: 20px; }
            #status { font-size: 0.65rem; letter-spacing: 2px; color: #555; margin-bottom: 10px; text-transform: uppercase; }
            #reply { font-size: 1rem; color: #ddd; line-height: 1.5; min-height: 50px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AI K1 NEURAL LINK</h1>
            <div class="orb-container" id="btnMic">
                <div class="orb"><div class="orb-inner"></div></div>
            </div>
            <div class="glass">
                <div id="status">Standby</div>
                <div id="reply">Klik bola untuk mulai mengobrol...</div>
            </div>
        </div>

        <script>
            const btn = document.getElementById('btnMic');
            const statusLabel = document.getElementById('status');
            const replyText = document.getElementById('reply');
            
            const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.lang = 'id-ID';

            btn.onclick = () => { 
                try { recognition.start(); } catch(e) {} 
            };

            recognition.onstart = () => {
                document.querySelector('.orb-container').classList.add('listening');
                statusLabel.innerText = "Mendengarkan...";
            };

            recognition.onresult = async (event) => {
                const text = event.results[0][0].transcript;
                document.querySelector('.orb-container').classList.remove('listening');
                statusLabel.innerText = "Berpikir...";
                
                const formData = new FormData();
                formData.append('user_id', 'k1_pilot_v1');
                formData.append('message', text);

                try {
                    const res = await fetch('/chat', { method: 'POST', body: formData });
                    const data = await res.json();
                    replyText.innerText = data.reply;
                    statusLabel.innerText = "AI Menjawab";

                    const utter = new SpeechSynthesisUtterance(data.reply.replace(/[*#_]/g, ""));
                    utter.lang = 'id-ID';
                    window.speechSynthesis.speak(utter);
                } catch(e) {
                    replyText.innerText = "Gagal menghubungi neural core.";
                }
            };

            recognition.onerror = () => {
                document.querySelector('.orb-container').classList.remove('listening');
                statusLabel.innerText = "Standby";
            };
        </script>
    </body>
    </html>
    """

# --- API CHAT ---
@app.post("/chat")
async def chat_endpoint(user_id: str = Form(...), message: str = Form(...), file: UploadFile = File(None)):
    history = await get_history(user_id)
    chat = model.start_chat(history=history)
    
    if file:
        img = PIL.Image.open(io.BytesIO(await file.read()))
        response = chat.send_message([message, img])
    else:
        response = chat.send_message(message)
        
    await save_history(user_id, chat.history)
    return {"reply": response.text}