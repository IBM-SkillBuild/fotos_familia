import psycopg2
import os

# Configuración de la base de datos PostgreSQL
PG_HOST = os.getenv('DATABASE_HOST', 'ep-divine-sea-a2tsh7q5.eu-central-1.pg.koyeb.app')
PG_USER = os.getenv('DATABASE_USER', 'koyeb-adm')
PG_PASSWORD = os.getenv('DATABASE_PASSWORD', 'npg_dGpMKX9j8qnm')
PG_DATABASE = os.getenv('DATABASE_NAME', 'koyebdb')
PG_PORT = 5432

try:
    # Conectar a la base de datos
    conn = psycopg2.connect(
        host=PG_HOST,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DATABASE,
        port=PG_PORT
    )
    
    cursor = conn.cursor()
    
    # Actualizar la secuencia de la tabla photos
    cursor.execute("SELECT setval('photos_id_seq', (SELECT MAX(id) FROM photos))")
    conn.commit()
    
    print("Secuencia de la tabla photos actualizada exitosamente")
    
except Exception as e:
    print(f"Error actualizando la secuencia: {e}")
finally:
    if conn:
        conn.close()