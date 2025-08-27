#!/usr/bin/env python3
"""
Script para generar iconos PWA desde una imagen base
Requiere Pillow: pip install Pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon_with_text(size, text="❤️", bg_color="#f0f0f0", text_color="black"):
    """Crear un icono con texto/emoji"""
    # Crear imagen con fondo
    img = Image.new('RGBA', (size, size), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Intentar usar una fuente del sistema
    try:
        # En Windows
        font_size = size // 3
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            # Fuente por defecto
            font = ImageFont.load_default()
        except:
            font = None
    
    # Calcular posición del texto centrado
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    else:
        text_width = len(text) * (size // 8)
        text_height = size // 4
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Dibujar el texto
    draw.text((x, y), text, fill=text_color, font=font)
    
    return img

def generate_pwa_icons():
    """Generar todos los iconos necesarios para PWA"""
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # Crear directorio si no existe
    os.makedirs('static/icons', exist_ok=True)
    
    print("Generando iconos PWA...")
    
    for size in sizes:
        print(f"Generando icono {size}x{size}...")
        
        # Crear icono
        icon = create_icon_with_text(size)
        
        # Guardar
        filename = f'static/icons/icon-{size}x{size}.png'
        icon.save(filename, 'PNG', optimize=True)
        print(f"OK Guardado: {filename}")
    
    # Crear favicon.ico (múltiples tamaños)
    print("Generando favicon.ico...")
    favicon_sizes = [16, 32, 48]
    favicon_images = []
    
    for size in favicon_sizes:
        favicon_images.append(create_icon_with_text(size))
    
    # Guardar favicon con múltiples tamaños
    favicon_images[0].save(
        'static/favicon.ico',
        format='ICO',
        sizes=[(size, size) for size in favicon_sizes]
    )
    print("OK Guardado: static/favicon.ico")
    
    # Crear apple-touch-icon
    print("Generando apple-touch-icon...")
    apple_icon = create_icon_with_text(180)
    apple_icon.save('static/apple-touch-icon.png', 'PNG', optimize=True)
    print("OK Guardado: static/apple-touch-icon.png")
    
    print("\n¡Todos los iconos PWA generados exitosamente!")
    print("\nIconos creados:")
    for size in sizes:
        print(f"  - icon-{size}x{size}.png")
    print("  - favicon.ico")
    print("  - apple-touch-icon.png")

if __name__ == "__main__":
    try:
        generate_pwa_icons()
    except ImportError:
        print("ERROR: Pillow no está instalado")
        print("Instala con: pip install Pillow")
    except Exception as e:
        print(f"ERROR generando iconos: {e}")
