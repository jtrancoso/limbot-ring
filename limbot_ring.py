"""
Automatización para descargar la última factura de Ring y enviarla por email.
Utiliza login programático con 2FA (TOTP) para ser 100% autónomo.
"""
import os
import smtplib
import pyotp
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env al inicio
load_dotenv()

# --- CONFIGURACIÓN (leída desde variables de entorno) ---
# Credenciales de Ring
RING_EMAIL = os.getenv("RING_EMAIL")
RING_PASSWORD = os.getenv("RING_PASSWORD")
RING_TOTP_SECRET = os.getenv("RING_TOTP_SECRET")
BILLING_URL = "https://account.ring.com/account/billing/history"

# Configuración del Navegador
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Configuración de Email
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# Directorios
DOWNLOAD_DIR = Path("/tmp/ring_invoices")

def do_login(page):
    """
    Versión final: Su única responsabilidad es completar el login y dejar
    la sesión establecida en la página a la que Ring redirija.
    """
    print("➡️  Iniciando sesión en Ring...")
    # ... (El código de navegación, cookies, análisis forense, email y contraseña es idéntico)...
    print("➡️  Navegando a la página de inicio...")
    page.goto("https://ring.com/es/es", wait_until="networkidle")

    try:
        page.locator("button:has-text('Aceptar')").click(timeout=5000)
        print("✅ Banner de cookies aceptado.")
        page.wait_for_timeout(1000)
    except Exception:
        print("⚠️  No se encontró el banner de cookies, continuando...")

    try:
        page.locator("a:has-text('Iniciar sesión'), a:has-text('Sign In')").first.click()
        page.wait_for_load_state("networkidle", timeout=20000)
        print("✅ Página de login cargada.")
    except Exception:
        print("⚠️  No se encontró/pulsó 'Iniciar sesión', asumiendo que ya estamos en la página correcta.")

    page.wait_for_timeout(3000)
    email_selector = "input[data-testid='input-form-field-sign-in-card'], input[name='username']"
    login_container = page
    if not page.locator(email_selector).count() > 0:
        for frame in page.frames[1:]:
            if frame.locator(email_selector).count() > 0:
                print(f"✅ ¡Formulario encontrado en el iframe con URL: {frame.url}!")
                login_container = frame
                break
    if not login_container:
        raise Exception("No se pudo localizar el formulario de login.")

    print("➡️  Rellenando email y contraseña...")
    login_container.locator(email_selector).fill(RING_EMAIL)
    login_container.locator("button[data-testid='submit-button-final-sign-in-card']").click()
    password_input = login_container.locator("input[type='password']")
    password_input.wait_for(state="visible", timeout=20000)
    password_input.fill(RING_PASSWORD)
    login_container.locator("button[data-testid='submit-button-final-sign-in-card']").click()
    print("✅ Credenciales enviadas.")

    print("➡️  Esperando a que la pantalla de 2FA sea visible...")
    two_fa_title_selector = "div[data-testid='two-fa-title-sign-in-card']"
    login_container.locator(two_fa_title_selector).wait_for(state="visible", timeout=20000)
    print("✅ Pantalla de 2FA detectada y lista.")

    print("➡️  Generando y rellenando código 2FA...")
    totp_selector = "input[data-testid='input-form-field-two-fa-sign-in-card']"
    totp_input = login_container.locator(totp_selector)
    totp = pyotp.TOTP(RING_TOTP_SECRET)
    code = totp.now()
    totp_input.fill(code)

    print("➡️  Enviando código 2FA y esperando la navegación de confirmación...")
    verify_button_selector = "button[data-testid='submit-button-final-sign-in-card']"
    with page.expect_navigation(wait_until="networkidle", timeout=30000):
        login_container.locator(verify_button_selector).click()
    
    # --- CAMBIO CLAVE ---
    # La función termina aquí. Su trabajo está hecho.
    print("✅ Login completado y sesión establecida.")


def download_latest_invoice() -> Path:
    """
    Versión final: Utiliza la URL de facturación correcta y es más persistente
    en la navegación post-login.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Ponlo en False para la última prueba
        context = browser.new_context(
            user_agent=UA,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            accept_downloads=True
        )
        page = context.new_page()

        try:
            # 1. Realizar el login. Nos dejará en el dashboard.
            do_login(page)

            print("➡️  Pausa de 2 segundos para asentar la sesión...")
            page.wait_for_timeout(2000)

            # --- NAVEGACIÓN ROBUSTA A LA URL CORRECTA ---
            print(f"➡️  Navegando a la página de facturación: {BILLING_URL}")
            # Hacemos dos intentos para asegurarnos de que llegamos
            for attempt in range(2):
                try:
                    page.goto(BILLING_URL, wait_until="networkidle")
                    # Verificamos si hemos llegado a la URL correcta o a una sub-página
                    page.wait_for_url("**/account/billing/**", timeout=15000)
                    print("✅ ¡Éxito! Estamos en la sección de facturación.")
                    break # Si llegamos, salimos del bucle
                except Exception as e:
                    print(f"⚠️  Intento {attempt + 1} fallido. Reintentando...")
                    if attempt == 1: # Si es el último intento y falla, lanzamos el error
                        raise e
            # ----------------------------------------------------

            # 2. Esperar a que la tabla de facturas esté cargada
            page.wait_for_selector("tbody tr", timeout=30000)

            # 3. Descargar la factura
            first_row = page.locator("tbody tr").first
            download_link = first_row.locator("a:has-text('Descargar'), button:has-text('Descargar')")
            
            with page.expect_download(timeout=30000) as download_info:
                download_link.click()
            
            download = download_info.value
            suggested_filename = download.suggested_filename or f"ring-factura-{datetime.now():%Y-%m}.pdf"
            save_path = DOWNLOAD_DIR / suggested_filename
            download.save_as(save_path)
            
            print(f"📄 Factura descargada con éxito en: {save_path}")
            return save_path

        except Exception as e:
            error_path = Path("/tmp/ring_error_screenshot.png")
            page.screenshot(path=str(error_path))
            print(f"🚨 ERROR: Ocurrió un fallo. Se ha guardado una captura en {error_path}")
            raise e
        finally:
            browser.close()


def send_invoice_by_email(pdf_path: Path):
    """Envía la factura en PDF como adjunto por email."""
    if not all([SMTP_USER, SMTP_PASSWORD, RECIPIENT_EMAIL]):
        print("⚠️  Faltan variables de entorno para el email. No se enviará correo.")
        return

    print(f"➡️  Preparando email para enviar a {RECIPIENT_EMAIL}...")
    
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"Factura de Ring - {datetime.now().strftime('%B %Y').capitalize()}"
    
    body = f"Se adjunta la última factura de Ring.\n\nUn besito, \n Limbot."
    msg.attach(MIMEText(body, "plain"))

    try:
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {pdf_path.name}")
            msg.attach(part)
    except FileNotFoundError:
        print(f"🚨 ERROR: No se encontró el fichero PDF en '{pdf_path}'.")
        return

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print(f"✅ Email enviado correctamente a {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"🚨 ERROR al enviar el email: {e}")


if __name__ == "__main__":
    try:
        # Paso 1: Descargar la factura
        invoice_file_path = download_latest_invoice()
        
        # Paso 2: Enviar la factura por email
        if invoice_file_path:
            send_invoice_by_email(invoice_file_path)
        
        print("\n🎉 Proceso completado con éxito.")

    except Exception as e:
        print(f"\n❌ El proceso falló con un error: {e}")