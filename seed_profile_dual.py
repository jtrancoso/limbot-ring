# seed_profile_dual.py
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("/tmp/ring-profile")  # mismo path que usa tu bot
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            user_agent=UA,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()

        # 1) Entra en ring.com y haz login ahí (si te lo pide)
        page.goto("https://ring.com/es/es", wait_until="networkidle")
        print("👉 Si ves 'Iniciar sesión/Sign in' en ring.com, pulsa y loguéate (con SMS si te lo pide).")
        input("Cuando veas que estás logueado en ring.com (tu nombre, etc.), pulsa ENTER aquí… ")

        # 2) Ahora ve al subdominio de account y confirma que NO te saca
        page.goto("https://account.ring.com/account/billing", wait_until="networkidle")
        print("👉 Si te pide solo contraseña, introdúcela. No debería pedir SMS.")
        input("Cuando VEAS la tabla de facturación en account.ring.com, pulsa ENTER aquí… ")

        ctx.close()
    print(f"✅ Perfil con cookies para ring.com y account.ring.com guardado en {PROFILE_DIR}")

if __name__ == "__main__":
    main()
