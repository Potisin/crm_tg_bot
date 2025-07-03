from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# Настройки
ACCESS_TOKEN = os.environ.get("AMO_ACCESS_TOKEN")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
AMO_DOMAIN = "https://shcherbakovxsizemoscow.amocrm.ru"

# Получение данных сделки и отправка в Telegram
@app.route("/", methods=["POST"])
def webhook():
    try:
        form = request.form.to_dict(flat=False)
        leads = json.loads(form.get("leads", [None])[0])

        lead_id = leads.get("add", [{}])[0].get("id")
        if not lead_id:
            return "ID сделки не найден", 400

        # Получаем данные сделки с контактом
        lead_response = requests.get(
            f"{AMO_DOMAIN}/api/v4/leads/{lead_id}?with=contacts",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}
        ).json()

        contact_id = lead_response.get("contacts", [{}])[0].get("id")

        # Получаем контакт (имя и телефон)
        contact_response = requests.get(
            f"{AMO_DOMAIN}/api/v4/contacts/{contact_id}?with=custom_fields",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}
        ).json()

        name = contact_response.get("name", "Без имени")
        phone = "Не указан"

        for field in contact_response.get("custom_fields_values", []):
            if field.get("field_name", "").lower() == "телефон":
                phone = field["values"][0].get("value")

        # Отправка в Telegram
        message = f"🔔 Новый лид!\n👤 Имя: {name}\n📞 Телефон: {phone}"
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message}
        )

        return "OK", 200

    except Exception as e:
        return f"Ошибка: {str(e)}", 500


@app.route("/", methods=["GET"])
def home():
    return "Бот работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
