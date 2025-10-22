# seed_profile.py
from pathlib import Path
from playwright.sync_api import sync_playwright

# Cambia esta ruta si quieres sembrar en otro sitio
PROFILE_DIR = Path("/tmp/ring-profile")
BILLING_URL = "https://account.ring.com/account/billing"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,              # ventana visible para que puedas hacer el login
            user_agent=UA,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        page.goto(BILLING_URL, wait_until="networkidle")
        print("\n👉 Completa el login en la ventana (incluido SMS 2FA) "
              "hasta que veas el Historial de facturación.")
        input("Cuando lo veas, vuelve a esta terminal y pulsa ENTER para guardar la sesión… ")
        ctx.close()
    print(f"✅ Perfil de sesión guardado en: {PROFILE_DIR}")

if __name__ == "__main__":
    main()
