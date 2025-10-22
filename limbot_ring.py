"""
limbot_ring.py
---------------
Playwright para Ring:
- keep_alive_visit(): refresca la sesión (no descarga).
- download_latest_invoice(): hace click en el primer "Descargar factura" y guarda el PDF.

Asume que la tabla de "Historial de facturación" está ordenada DESC (más reciente arriba).
"""

import os
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Directorios (en Cloud Run, /tmp es efímero)
DOWNLOAD_DIR = Path("/tmp/downloads")
PROFILE_DIR  = Path("/tmp/ring-profile")

# URL: en muchas cuentas la página buena es account.ring.com
BILLING_URL  = os.getenv("RING_BILLING_URL", "https://account.ring.com/account/billing")

# Identidad estable del “dispositivo”
UA = os.getenv("BROWSER_UA", (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
))

LOCALE = os.getenv("BROWSER_LOCALE", "es-ES")
TZ_ID  = os.getenv("BROWSER_TZ", "Europe/Madrid")

RING_PASSWORD = os.getenv("RING_PASSWORD")
RING_EMAIL = os.getenv("RING_EMAIL")

def ensure_dirs() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

def _ensure_on_billing(page):
    """Intenta dos veces llegar a Billing (a veces el primer salto te deja en ring.com)."""
    for _ in range(2):
        if "account.ring.com/account/billing" in page.url:
            return
        page.goto(BILLING_URL, wait_until="networkidle")


def _open_context(p):
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=True,
        accept_downloads=True,
        viewport={"width": 1400, "height": 900},
        user_agent=UA,
        locale=LOCALE,
        timezone_id=TZ_ID,
    )

def _is_logged_in(page) -> bool:
    html = page.content().lower()
    return not ("sign in" in html or "iniciar sesión" in html)

DEBUG = os.getenv("LIMBOT_DEBUG", "0") == "1"

def _wait_billing_table(page):
    """
    Espera robusta sin depender de atributos de tabla:
    - asegura estar en Billing
    - espera ver el encabezado 'Detalles de la factura' o, como fallback, al menos una fila en <tbody>.
    """
    _ensure_on_billing(page)
    try:
        page.wait_for_load_state("networkidle", timeout=25000)
    except PWTimeout:
        pass

    # 1) intenta por encabezado visible
    try:
        page.wait_for_selector("thead th:has-text('Detalles de la factura')", timeout=12000)
        return
    except PWTimeout:
        pass

    # 2) fallback: espera a que exista al menos una fila de tbody
    try:
        page.wait_for_selector("tbody tr", timeout=12000)
        return
    except PWTimeout:
        pass

    # 3) último intento: cualquier “Descargar factura” visible (por si no hay thead)
    page.wait_for_selector("a:visible:has-text('Descargar factura'), a:visible:has-text('Descargar')", timeout=12000)


def keep_alive_visit() -> None:
    ensure_dirs()
    with sync_playwright() as p:
        ctx = _open_context(p)
        page = ctx.new_page()
        page.goto(BILLING_URL, wait_until="networkidle")
        _ensure_on_billing(page)
        _solve_verification_iframe(page)
        
        if not _is_logged_in(page):
            ctx.close()
            raise RuntimeError(
                "La sesión de Ring ha caducado (pide login/2FA). "
                "Reautentica localmente y vuelve a subir el perfil de sesión."
            )

        _wait_billing_table(page)   # ya garantiza que la tabla y las filas existen
        page.reload(wait_until="networkidle")   # refresca cookies/tokens
        ctx.close()

def _solve_verification_iframe(page) -> bool:
    """Si aparece el iframe /users/challenge, rellena password (y email si procede) y envía."""
    from playwright.sync_api import TimeoutError as PWTimeout
    try:
        page.wait_for_selector("iframe[src*='/users/challenge'], iframe[title*='Verifica']", timeout=5000)
    except PWTimeout:
        return True  # no hay reto

    fr = None
    for f in page.frames:
        if "/users/challenge" in (f.url or ""):
            fr = f; break
    if fr is None:
        return False

    # email (si lo muestra)
    try:
        email_in = fr.locator("input[type='email'], input[name='email']").first
        if email_in.count() > 0 and RING_EMAIL:
            email_in.fill(RING_EMAIL)
    except Exception:
        pass

    # password (a veces aparece tras un 'Continuar')
    pwd = fr.locator("input[type='password'], input[name='password']").first
    if pwd.count() == 0:
        cont = fr.locator("button:has-text('Continuar'), button:has-text('Continue'), button[type='submit']").first
        if cont.count() > 0:
            cont.click()
            page.wait_for_timeout(600)
            pwd = fr.locator("input[type='password'], input[name='password']").first

    if pwd.count() == 0:
        return False
    if not RING_PASSWORD:
        raise RuntimeError("Define RING_PASSWORD para resolver el reto de Ring.")

    # algunos inputs “controlados” se llevan mejor con type()
    try:
        pwd.fill("")
        pwd.type(RING_PASSWORD, delay=40)
    except Exception:
        fr.evaluate("el => el.value=''", pwd)
        pwd.type(RING_PASSWORD, delay=40)

    submit = fr.locator(
        "button[type='submit'], input[type='submit'], "
        "button:has-text('Verificar'), button:has-text('Verify'), "
        "button:has-text('Continuar'), button:has-text('Continue')"
    ).first
    if submit.count() == 0:
        return False
    submit.click()

    try:
        page.wait_for_selector("iframe[src*='/users/challenge'], iframe[title*='Verifica']",
                               state="detached", timeout=15000)
    except Exception:
        page.wait_for_timeout(800)
    # si no está, lo dimos por resuelto
    return True

def download_latest_invoice() -> Path:
    ensure_dirs()
    with sync_playwright() as p:
        ctx = _open_context(p)
        page = ctx.new_page()
        page.goto(BILLING_URL, wait_until="networkidle")

        if not _is_logged_in(page):
            ctx.close()
            raise RuntimeError("Sesión Ring no válida. Reautentica y sube el perfil a GCS.")

        # resuelve overlay si aparece
        _solve_verification_iframe(page)

        # espera filas del historial
        page.wait_for_selector("tbody tr", timeout=30000)

        # primera fila (más reciente) → última celda (Detalles) → primer <a>/<button>
        row = page.locator("tbody tr").first
        last_cell = row.locator("td").last
        cell_handle = last_cell.element_handle(timeout=5000)
        if cell_handle is None:
            ctx.close(); raise RuntimeError("No pude obtener la celda de 'Detalles de la factura'.")

        link_handle = cell_handle.query_selector("a,button")
        if link_handle is None:
            last_cell.click(); page.wait_for_timeout(300)
            link_handle = cell_handle.query_selector("a,button")
        if link_handle is None:
            # fallback: busca en toda la fila
            row_handle = row.element_handle()
            if row_handle:
                link_handle = row_handle.query_selector("a,button")
        if link_handle is None:
            ctx.close(); raise RuntimeError("No encontré enlace/botón de descarga en la primera fila.")

        # intenta descargar; si salta el overlay justo al clicar, resuélvelo y reintenta
        def do_click():
            with page.expect_download(timeout=45000) as dl_info:
                link_handle.click()
            return dl_info.value

        try:
            download = do_click()
        except Exception:
            if not _solve_verification_iframe(page):
                ctx.close(); raise
            download = do_click()

        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suggested = download.suggested_filename or f"ring-invoice-{stamp}.pdf"
        target = DOWNLOAD_DIR / suggested
        download.save_as(str(target))
        ctx.close()
        return target