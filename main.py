import os
from fastapi import FastAPI, Request
import httpx
from openai import OpenAI
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

app = FastAPI()

# --- Конфигурация из .env ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GREEN_API_ID_INSTANCE = os.getenv("GREEN_API_ID_INSTANCE")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Словарь для хранения истории сообщений каждого клиента
chat_histories = {}

SYSTEM_PROMPT = """
Ты — вежливый, профессиональный и клиентоориентированный ИИ-менеджер компании "TULPAR SERVICE" (автосервис по кузовному ремонту, детейлингу и оклейке в Астане, ул. Бейсекова 4/2).

БАЗА ЗНАНИЙ И ПРАЙС-ЛИСТ:
1. Кузовной ремонт:
- Покраска подетально: 60 000 тг за 1 деталь.
- Полная покраска кузова: от 500 000 тг (зависит от типа кузова). БОНУС: При полной покраске химчистка салона в подарок!
- Выпрямление кузова (PDR): 10 000 тг за 1 точку.
- Полировка: от 60 000 тг (зависит от типа кузова). Доп. опция: керамическое покрытие +20 000 тг к цене.

2. Бронепленка (Антигравийная защита):
- Люкс пакет: 240 000 тг (капот, два крыла, бампер, фары, перед крыши на 20 см). БОНУС: 3D полики в салон в подарок!
- Премиум пакет: от 500 000 тг (полная оклейка кузова). БОНУС: 3D полики в салон в подарок!
- Матовый сатин: от 600 000 тг (полная оклейка кузова матовой пленкой). БОНУС: 3D полики в салон в подарок!

3. Химчистка:
- Без разбора салона: от 40 000 тг (зависит от типа кузова).
- С разбором: от 60 000 тг.

4. Шумоизоляция:
- Полная шумоизоляция авто: от 250 000 тг (возможна частичная).

5. Аксессуары и коврики:
- Авто полики (коврики): от 40 000 тг (в зависимости от материала).
- Чехлы на сиденья: Индивидуальный пошив от 90 000 тг, универсальные от 40 000 тг.
- Накидки на панель: от 8 000 тг.

ПРАВИЛА ОТВЕТОВ:
1. Строго опирайся на этот прайс-лист. Если цены нет, не придумывай её, а предложи уточнить у мастера.
2. Всегда упоминай акции и подарки (химчистка при покраске, полики при бронепленке).
3. ЯЗЫКОВАЯ АДАПТАЦИЯ (ОЧЕНЬ ВАЖНО): Всегда отвечай на том языке, на котором обратился клиент. Если клиент пишет на казахском языке, но использует русские термины (например, "полировка", "шумоизоляция", "бронепленка"), органично используй их в ответе на казахском языке, подстраиваясь под клиента.
"""

def send_telegram_alert(phone: str, text: str):
    """Отправка уведомления в Telegram о новом обращении"""
    if not TELEGRAM_BOT_TOKEN:
        return
    
    tg_message = (
        "🔔 **Новое сообщение в WhatsApp!**\n\n"
        f"📱 **Номер:** `{phone}`\n"
        f"💬 **Текст:** {text}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": tg_message,
        "parse_mode": "Markdown"
    }
    try:
        httpx.post(url, json=payload, timeout=5.0)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request):
    data = await request.json()
    
    if data.get("typeWebhook") == "incomingMessageReceived":
        message_data = data.get("messageData", {})
        
        if message_data.get("typeMessage") == "textMessage":
            chat_id = data.get("senderData", {}).get("chatId", "")
            text_message = message_data.get("textMessageData", {}).get("textMessage", "").strip()
            
            phone = chat_id.split("@")[0] if "@" in chat_id else chat_id
            
            if chat_id and text_message:
                send_telegram_alert(phone, text_message)
                handle_ai_response(chat_id, text_message)
                
    return {"status": "ok"}

def handle_ai_response(chat_id: str, user_text: str):
    try:
        if chat_id not in chat_histories:
            chat_histories[chat_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        
        chat_histories[chat_id].append({"role": "user", "content": user_text})
        
        if len(chat_histories[chat_id]) > 11:
            chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-10:]

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_histories[chat_id],
            temperature=0.3
        )
        
        reply_text = response.choices[0].message.content.strip()
        chat_histories[chat_id].append({"role": "assistant", "content": reply_text})

        send_to_whatsapp(chat_id, reply_text)

    except Exception as e:
        print(f"Ошибка при обращении к OpenAI: {e}")

def send_to_whatsapp(chat_id: str, message: str):
    url = f"https://api.green-api.com/waInstance{GREEN_API_ID_INSTANCE}/sendMessage/{GREEN_API_TOKEN}"
    payload = {
        "chatId": chat_id,
        "message": message
    }
    httpx.post(url, json=payload)