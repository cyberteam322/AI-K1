import os
import io
import PIL.Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse # Tambahkan ini
from pydantic import BaseModel
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- KONFIGURASI ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.ai_k1_db

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Kamu AI K1, asisten koding & fitness. Bicara singkat, natural, dan ingat konteks."
)

# --- FUNGSI DATABASE ---
async def get_chat_history(user_id: str):
    doc = await db.history.find_one({"user_id": user_id})
    return doc["messages"] if doc else []

async def save_chat_history(user_id: str, messages: list):
    await db.history.update_one(
        {"user_id": user_id},
        {"$set": {"messages": messages}},
        upsert=True
    )

# --- TAMPILAN UI (Halaman Utama) ---
@app.get("/", response_class=HTMLResponse)
async def read_items():
    # Masukkan kode HTML canggih yang saya kirim sebelumnya di sini
    # Untuk sementara saya buatkan versi simpel agar kamu bisa tes dulu
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI K1 CORE</title>
        <style>
            body { background: #050505; color: #00f2ff; font-family: sans-serif; text-align: center; padding-top: 50px; }
            .orb { width: 100px; height: 100px; background: #00f2ff; border-radius: 50%; margin: auto; box-shadow: 0 0 50px #00f2ff; }
        </style>
    </head>
    <body>
        <div class="orb"></div>
        <h1>AI K1 NEURAL LINK ACTIVE</h1>
        <p>Sistem sudah online dan terhubung ke MongoDB.</p>
    </body>
    </html>
    """

# --- ENDPOINT CHAT ---
@app.post("/chat")
async def chat_endpoint(user_id: str = Form(...), message: str = Form(...), file: UploadFile = File(None)):
    history = await get_chat_history(user_id)
    chat = model.start_chat(history=history)
    
    try:
        if file:
            img_data = await file.read()
            img = PIL.Image.open(io.BytesIO(img_data))
            response = chat.send_message([message, img])
        else:
            response = chat.send_message(message)
        
        await save_chat_history(user_id, chat.history)
        return {"reply": response.text}
    except Exception as e:
        return {"error": str(e)}