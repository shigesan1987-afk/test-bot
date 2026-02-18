from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============================
# 日本語フォント登録（Yu Gothic）
# ============================
pdfmetrics.registerFont(TTFont('YuGothic', 'C:/Windows/Fonts/YuGothR.ttc'))

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = "LINE_CHANNEL_ACCESS_TOKEN"
LINE_CHANNEL_SECRET = "LINE_CHANNEL_SECRET"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_state = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_state:
        user_state[user_id] = {"step": 0, "items": []}

    state = user_state[user_id]

    # 開始
    if text == "しおり作成":
        state["step"] = 1
        state["items"] = []
        line_bot_api.reply_message(event.reply_token, TextSendMessage("日付を入力してください（例: 2025-03-12）"))
        return

    # 日付
    if state["step"] == 1:
        state["date"] = text
        state["step"] = 2
        line_bot_api.reply_message(event.reply_token, TextSendMessage("場所を入力してください"))
        return

    # 場所
    if state["step"] == 2:
        state["place"] = text
        state["step"] = 3
        line_bot_api.reply_message(event.reply_token, TextSendMessage("メモを入力してください"))
        return

    # メモ → 旅程追加
    if state["step"] == 3:
        state["memo"] = text

        state["items"].append({
            "date": state["date"],
            "place": state["place"],
            "memo": state["memo"]
        })

        state["step"] = 4
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("旅程を追加しますか？（はい / いいえ）")
        )
        return

    # 追加するかどうか
    if state["step"] == 4:

        # 「はい」
        if text.startswith("はい"):
            state["step"] = 1
            line_bot_api.reply_message(event.reply_token, TextSendMessage("次の日付を入力してください"))
            return

        # 「いいえ」
        elif text.startswith("いいえ"):
            pdf_path = generate_pdf(state["items"])
            pdf_url = request.url_root + "static/itinerary.pdf"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(f"PDFを作成しました。\nこちらからダウンロードできます：\n{pdf_url}")
            )

            user_state[user_id] = {"step": 0, "items": []}
            return

        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage("「はい」か「いいえ」で答えてください"))
            return


# ============================
# PDF 生成（日本語フォント対応）
# ============================
def generate_pdf(items):
    os.makedirs("static", exist_ok=True)
    pdf_path = "static/itinerary.pdf"

    pdf = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    y = height - 20 * mm
    pdf.setFont("YuGothic", 18)
    pdf.drawString(20 * mm, y, "旅行のしおり")
    y -= 15 * mm

    pdf.setFont("YuGothic", 12)

    items = sorted(items, key=lambda x: x["date"])

    for item in items:
        date = item["date"]
        place = item["place"]
        memo = item["memo"]

        if y < 40 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("YuGothic", 12)

        pdf.drawString(20 * mm, y, f"■ {date}")
        y -= 7 * mm
        pdf.drawString(25 * mm, y, f"場所: {place}")
        y -= 7 * mm
        if memo:
            pdf.drawString(25 * mm, y, f"メモ: {memo}")
            y -= 7 * mm

        maps_url = f"https://www.google.com/maps/search/?api=1&query={place}"
        pdf.setFont("YuGothic", 9)
        pdf.drawString(25 * mm, y, maps_url)
        pdf.setFont("YuGothic", 12)

        # QRコード生成（ImageReaderで確実に動く）
        qr = qrcode.make(maps_url)
        qr_buffer = io.BytesIO()
        qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        qr_image = ImageReader(qr_buffer)
        pdf.drawImage(qr_image, 150 * mm, y - 5 * mm, width=25 * mm, height=25 * mm)

        y -= 30 * mm

    pdf.save()
    return pdf_path


if __name__ == "__main__":

    app.run(port=8000)
