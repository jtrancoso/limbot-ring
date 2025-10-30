from flask import Flask, request
import os
import base64
import limbot_ring  # tu módulo

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Cloud Run Flask funcionando correctamente", 200

@app.route("/run", methods=["POST"])
def run_automation():
    try:
        envelope = request.get_json()
        if envelope and "message" in envelope:
            data = envelope["message"].get("data")
            if data:
                msg = base64.b64decode(data).decode("utf-8").strip()
                print(f"📨 Mensaje Pub/Sub recibido: {msg}")

        print("🚀 Iniciando automatización de factura...")
        invoice = limbot_ring.download_latest_invoice()
        if invoice:
            limbot_ring.send_invoice_by_email(invoice)
        print("✅ Proceso completado correctamente.")
        return "Success", 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return str(e), 500


if __name__ == "__main__":
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/ms-playwright"
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)