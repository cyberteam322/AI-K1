import os
import io
import PIL.Image
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Agar bisa diakses dari file HTML lokal/hosting lain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konfigurasi API & Database
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.ai_k1_db

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Kamu AI K1, asisten koding & fitness. Bicara singkat, natural, dan ingat konteks."
)

# Fungsi Memori
async def get_chat_history(user_id: str):
    doc = await db.history.find_one({"user_id": user_id})
    return doc["messages"] if doc else []

async def save_chat_history(user_id: str, messages: list):
    await db.history.update_one(
        {"user_id": user_id},
        {"$set": {"messages": messages}},
        upsert=True
    )

@app.post("/chat")
async def chat_endpoint(user_id: str = Form(...), message: str = Form(...), file: UploadFile = File(None)):
    # 1. Ambil memori lama
    history = await get_chat_history(user_id)
    chat = model.start_chat(history=history)
    
    try:
        if file:
            # Mode Vision (Lihat Gambar)
            img_data = await file.read()
            img = PIL.Image.open(io.BytesIO(img_data))
            response = chat.send_message([message, img])
        else:
            # Mode Chat Biasa
            response = chat.send_message(message)
        
        # 2. Simpan memori baru (termasuk jawaban AI)
        await save_chat_history(user_id, chat.history)
        
        return {"reply": response.text}
    except Exception as e:
        return {"error": str(e)}