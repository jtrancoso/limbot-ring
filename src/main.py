# main.py
import limbot_ring

def run_ring_automation(event, context):
    """
    Punto de entrada para la Cloud Function.
    Este es el nombre de la función que Google Cloud ejecutará.
    """
    print("🚀 Cloud Function triggered. Starting Ring invoice automation...")
    
    try:
        # Paso 1: Descargar la factura
        invoice_file_path = limbot_ring.download_latest_invoice()
        
        # Paso 2: Enviar la factura por email
        if invoice_file_path:
            limbot_ring.send_invoice_by_email(invoice_file_path)
        
        print("✅ Process completed successfully.")
    
    except Exception as e:
        # Imprimir el error es crucial para poder verlo en los logs de Google Cloud
        print(f"❌ An error occurred during the process: {e}")
        # Relanzar la excepción para que la ejecución se marque como fallida
        raise e