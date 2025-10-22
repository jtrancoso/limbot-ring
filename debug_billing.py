# debug_billing.py
from pathlib import Path
from playwright.sync_api import sync_playwright
import os

PROFILE_DIR = Path("/tmp/ring-profile")
BILLING_URL = os.getenv("RING_BILLING_URL", "https://account.ring.com/account/billing")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False, slow_mo=150,
            user_agent=UA, locale="es-ES", timezone_id="Europe/Madrid",
            accept_downloads=True, viewport={"width":1400,"height":900},
        )
        page = ctx.new_page()

        def goto_billing():
            page.goto(BILLING_URL, wait_until="networkidle")
            print("URL actual:", page.url)

        goto_billing()
        # Si te llevó a ring.com, vuelve a saltar a Billing tras password-only
        if "ring.com/" in page.url and "account.ring.com" not in page.url:
            input("Parece que te ha llevado a ring.com. Si te pide contraseña, métela y luego ENTER para reintentar… ")
            goto_billing()

        input("¿Ves la tabla con 'Detalles de la factura'? Si sí, ENTER para cerrar… ")
        ctx.close()

if __name__ == "__main__":
    main()
