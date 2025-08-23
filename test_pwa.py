#!/usr/bin/env python3
"""
Script para probar la funcionalidad PWA
"""

import requests
import json
from urllib.parse import urljoin

def test_pwa_files(base_url="http://localhost:5000"):
    """Probar que todos los archivos PWA están disponibles"""
    
    files_to_test = [
        "/static/manifest.json",
        "/static/sw.js",
        "/static/favicon.ico",
        "/static/apple-touch-icon.png",
        "/static/icons/icon-192x192.png",
        "/static/icons/icon-512x512.png",
        "/static/css/pwa.css",
        "/static/js/pwa.js",
        "/offline"
    ]
    
    print("🧪 Probando archivos PWA...")
    print(f"Base URL: {base_url}")
    print("-" * 50)
    
    results = []
    
    for file_path in files_to_test:
        url = urljoin(base_url, file_path)
        try:
            response = requests.get(url, timeout=5)
            status = "✅ OK" if response.status_code == 200 else f"❌ Error {response.status_code}"
            results.append((file_path, response.status_code, status))
            print(f"{status:10} {file_path}")
        except requests.exceptions.RequestException as e:
            results.append((file_path, 0, f"❌ Error: {str(e)}"))
            print(f"❌ Error   {file_path} - {str(e)}")
    
    print("-" * 50)
    
    # Resumen
    successful = len([r for r in results if r[1] == 200])
    total = len(results)
    
    print(f"📊 Resumen: {successful}/{total} archivos disponibles")
    
    if successful == total:
        print("🎉 ¡Todos los archivos PWA están disponibles!")
    else:
        print("⚠️  Algunos archivos no están disponibles. Verifica el servidor.")
    
    return results

def test_manifest_content(base_url="http://localhost:5000"):
    """Probar el contenido del manifest.json"""
    
    print("\n🔍 Probando contenido del manifest...")
    
    try:
        response = requests.get(urljoin(base_url, "/static/manifest.json"))
        if response.status_code == 200:
            manifest = response.json()
            
            required_fields = ["name", "short_name", "start_url", "display", "theme_color", "icons"]
            
            print("Campos requeridos:")
            for field in required_fields:
                if field in manifest:
                    print(f"  ✅ {field}: {manifest[field] if field != 'icons' else f'{len(manifest[field])} iconos'}")
                else:
                    print(f"  ❌ {field}: Faltante")
            
            # Verificar iconos
            if "icons" in manifest:
                print(f"\nIconos disponibles:")
                for icon in manifest["icons"]:
                    print(f"  📱 {icon['sizes']} - {icon['src']}")
            
            return True
        else:
            print(f"❌ Error obteniendo manifest: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def show_pwa_checklist():
    """Mostrar checklist para PWA"""
    
    print("\n📋 Checklist PWA:")
    print("-" * 50)
    
    checklist = [
        "✅ Manifest.json configurado",
        "✅ Service Worker registrado",
        "✅ Iconos en múltiples tamaños (72px a 512px)",
        "✅ Meta tags para móviles",
        "✅ Apple touch icons",
        "✅ Tema de color definido",
        "✅ Página offline",
        "✅ HTTPS (requerido para producción)",
        "✅ Responsive design",
        "✅ Funcionalidad offline básica"
    ]
    
    for item in checklist:
        print(f"  {item}")
    
    print("\n📱 Para probar en Android:")
    print("  1. Abre Chrome en tu móvil")
    print("  2. Navega a tu aplicación")
    print("  3. Toca el menú (⋮) > 'Añadir a pantalla de inicio'")
    print("  4. Confirma la instalación")
    
    print("\n🍎 Para probar en iOS:")
    print("  1. Abre Safari en tu iPhone/iPad")
    print("  2. Navega a tu aplicación")
    print("  3. Toca el botón compartir")
    print("  4. Selecciona 'Añadir a pantalla de inicio'")

if __name__ == "__main__":
    import sys
    
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    # Probar archivos
    results = test_pwa_files(base_url)
    
    # Probar manifest
    test_manifest_content(base_url)
    
    # Mostrar checklist
    show_pwa_checklist()
    
    print(f"\n🚀 Para probar la PWA, visita: {base_url}")
    print("💡 Tip: Usa las herramientas de desarrollador de Chrome > Application > Manifest")