from flask import Flask, request
import requests
import json
import os
import traceback
import time

app = Flask(__name__)

# === Постоянные настройки ===
AMO_DOMAIN = "https://shcherbakovxsizemoscow.amocrm.ru"
TOKEN_FILE = "amo_tokens.json"

# === Настройки Telegram ===
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# === OAuth2 данные для обновления токена ===
CLIENT_ID = os.environ.get("AMO_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AMO_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("AMO_REDIRECT_URI")

# === Получение и обновление access_token ===
def get_tokens():
    if not os.path.exists(TOKEN_FILE):
        raise Exception("Файл с токенами не найден")
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f)

def refresh_access_token():
    tokens = get_tokens()
    response = requests.post(f"{AMO_DOMAIN}/oauth2/access_token", json={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "redirect_uri": REDIRECT_URI
    })
    new_tokens = response.json()
    save_tokens(new_tokens)
    return new_tokens["access_token"]

def get_valid_access_token():
    tokens = get_tokens()
    return tokens["access_token"]

def authorized_get(url):
    token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 401:
        print("🔄 Токен просрочен, обновляем...")
        token = refresh_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers)
    return response

# === Обработка вебхука от amoCRM ===
@app.route("/", methods=["POST"])
def webhook():
    try:
        print("🔔 Получен POST-запрос от amoCRM")
        form = request.form.to_dict(flat=False)
        print("📥 Данные формы:", form)

        lead_id = form.get("leads[add][0][id]", [None])[0]
        print(f"➡️ ID сделки: {lead_id}")

        if not lead_id:
            return "ID сделки не найден", 400

        # Получение сделки с контактом
        lead_response = authorized_get(f"{AMO_DOMAIN}/api/v4/leads/{lead_id}?with=contacts")
        lead_data = lead_response.json()
        print("📄 Ответ от /leads:", lead_data)

        contact_id = (
            lead_data.get("_embedded", {})
            .get("contacts", [{}])[0]
            .get("id")
        )
        print(f"👤 ID контакта: {contact_id}")

        if not contact_id:
            return "Контакт не найден", 400

        # Получение контакта
        contact_response = authorized_get(f"{AMO_DOMAIN}/api/v4/contacts/{contact_id}?with=custom_fields")
        contact_data = contact_response.json()
        print("👤 Ответ от /contacts:", contact_data)

        name = contact_data.get("name", "Без имени")
        phone = "Не указан"

        for field in contact_data.get("custom_fields_values", []):
            if field.get("field_name", "").lower() == "телефон":
                phone = field["values"][0].get("value")
                break

        message = f"🔔 Новый лид!\n👤 Имя: {name}\n📞 Телефон: {phone}"
        print("📤 Отправка в Telegram:", message)

        tg_response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message}
        )
        print("✅ Ответ от Telegram:", tg_response.text)

        return "OK", 200

    except Exception as e:
        print("❌ Ошибка в webhook:")
        traceback.print_exc()
        return f"Ошибка: {str(e)}", 500

@app.route("/", methods=["GET"])
def home():
    return "Бот работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
