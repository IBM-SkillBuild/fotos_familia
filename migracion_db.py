#!/usr/bin/env python3
"""
Script para migrar datos de SQLite a PostgreSQL
"""

import sqlite3
import psycopg2
import os
from datetime import datetime
import sys

# Configuración de la base de datos SQLite (origen)
SQLITE_DB_PATH = 'users.db'

# Configuración de la base de datos PostgreSQL (destino)
PG_HOST = os.getenv('DATABASE_HOST', 'ep-divine-sea-a2tsh7q5.eu-central-1.pg.koyeb.app')
PG_USER = os.getenv('DATABASE_USER', 'koyeb-adm')
PG_PASSWORD = os.getenv('DATABASE_PASSWORD', 'npg_dGpMKX9j8qnm')
PG_DATABASE = os.getenv('DATABASE_NAME', 'koyebdb')
PG_PORT = 5432

def connect_sqlite():
    """Conectar a la base de datos SQLite"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        print(f"Conectado a SQLite: {SQLITE_DB_PATH}")
        return conn
    except Exception as e:
        print(f"Error conectando a SQLite: {e}")
        sys.exit(1)

def connect_postgres():
    """Conectar a la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DATABASE,
            port=PG_PORT
        )
        print(f"Conectado a PostgreSQL: {PG_HOST}")
        return conn
    except Exception as e:
        print(f"Error conectando a PostgreSQL: {e}")
        sys.exit(1)

def create_tables(pg_conn):
    """Crear las tablas en PostgreSQL"""
    try:
        cursor = pg_conn.cursor()
        
        # Crear tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                alias TEXT,
                phone TEXT,
                email TEXT,
                access_token TEXT,
                token_expires TIMESTAMP,
                verification_code TEXT,
                code_expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_interaction_days INTEGER DEFAULT 1
            )
        ''')
        
        # Crear tabla de sesiones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                token TEXT UNIQUE,
                expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Crear tabla de códigos de verificación
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                name TEXT,
                code TEXT NOT NULL,
                expires TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Crear tabla de fotos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                nombre TEXT,
                nombre_archivo TEXT NOT NULL,
                categoria TEXT,
                mes INTEGER,
                año INTEGER,
                personas_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Crear tabla de personas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personas (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                imagen TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Crear índices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verification_codes_email ON verification_codes(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verification_codes_code ON verification_codes(code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_año ON photos(año)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_mes ON photos(mes)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_personas_nombre ON personas(nombre)')
        
        pg_conn.commit()
        print("Tablas creadas exitosamente en PostgreSQL")
    except Exception as e:
        print(f"Error creando tablas en PostgreSQL: {e}")
        pg_conn.rollback()
        sys.exit(1)

def migrate_users(sqlite_conn, pg_conn):
    """Migrar tabla de usuarios"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Obtener datos de usuarios de SQLite
        sqlite_cursor.execute('SELECT * FROM users')
        users = sqlite_cursor.fetchall()
        
        # Insertar en PostgreSQL
        for user in users:
            pg_cursor.execute('''
                INSERT INTO users (
                    id, name, alias, phone, email, access_token, token_expires,
                    verification_code, code_expires, created_at, updated_at,
                    last_interaction_date, total_interaction_days
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    alias = EXCLUDED.alias,
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    access_token = EXCLUDED.access_token,
                    token_expires = EXCLUDED.token_expires,
                    verification_code = EXCLUDED.verification_code,
                    code_expires = EXCLUDED.code_expires,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at,
                    last_interaction_date = EXCLUDED.last_interaction_date,
                    total_interaction_days = EXCLUDED.total_interaction_days
            ''', (
                user['id'], user['name'], user['alias'], user['phone'], user['email'],
                user['access_token'], user['token_expires'], user['verification_code'],
                user['code_expires'], user['created_at'], user['updated_at'],
                user['last_interaction_date'], user['total_interaction_days']
            ))
        
        pg_conn.commit()
        print(f"Migrados {len(users)} usuarios")
    except Exception as e:
        print(f"Error migrando usuarios: {e}")
        pg_conn.rollback()
        sys.exit(1)

def migrate_sessions(sqlite_conn, pg_conn):
    """Migrar tabla de sesiones"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Obtener datos de sesiones de SQLite
        sqlite_cursor.execute('SELECT * FROM sessions')
        sessions = sqlite_cursor.fetchall()
        
        # Insertar en PostgreSQL
        for session in sessions:
            pg_cursor.execute('''
                INSERT INTO sessions (
                    id, user_id, token, expires, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    token = EXCLUDED.token,
                    expires = EXCLUDED.expires,
                    created_at = EXCLUDED.created_at
            ''', (
                session['id'], session['user_id'], session['token'],
                session['expires'], session['created_at']
            ))
        
        pg_conn.commit()
        print(f"Migradas {len(sessions)} sesiones")
    except Exception as e:
        print(f"Error migrando sesiones: {e}")
        pg_conn.rollback()
        sys.exit(1)

def migrate_verification_codes(sqlite_conn, pg_conn):
    """Migrar tabla de códigos de verificación"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Obtener datos de códigos de verificación de SQLite
        sqlite_cursor.execute('SELECT * FROM verification_codes')
        codes = sqlite_cursor.fetchall()
        
        # Insertar en PostgreSQL
        for code in codes:
            pg_cursor.execute('''
                INSERT INTO verification_codes (
                    id, email, name, code, expires, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    code = EXCLUDED.code,
                    expires = EXCLUDED.expires,
                    created_at = EXCLUDED.created_at
            ''', (
                code['id'], code['email'], code['name'],
                code['code'], code['expires'], code['created_at']
            ))
        
        pg_conn.commit()
        print(f"Migrados {len(codes)} códigos de verificación")
    except Exception as e:
        print(f"Error migrando códigos de verificación: {e}")
        pg_conn.rollback()
        sys.exit(1)

def migrate_photos(sqlite_conn, pg_conn):
    """Migrar tabla de fotos"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Obtener datos de fotos de SQLite
        sqlite_cursor.execute('SELECT * FROM photos')
        photos = sqlite_cursor.fetchall()
        
        # Insertar en PostgreSQL
        for photo in photos:
            pg_cursor.execute('''
                INSERT INTO photos (
                    id, user_id, nombre, nombre_archivo, categoria,
                    mes, año, personas_ids, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    nombre = EXCLUDED.nombre,
                    nombre_archivo = EXCLUDED.nombre_archivo,
                    categoria = EXCLUDED.categoria,
                    mes = EXCLUDED.mes,
                    año = EXCLUDED.año,
                    personas_ids = EXCLUDED.personas_ids,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at
            ''', (
                photo['id'], photo['user_id'], photo['nombre'], photo['nombre_archivo'],
                photo['categoria'], photo['mes'], photo['año'], photo['personas_ids'],
                photo['created_at'], photo['updated_at']
            ))
        
        pg_conn.commit()
        print(f"Migradas {len(photos)} fotos")
    except Exception as e:
        print(f"Error migrando fotos: {e}")
        pg_conn.rollback()
        sys.exit(1)

def migrate_personas(sqlite_conn, pg_conn):
    """Migrar tabla de personas"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Obtener datos de personas de SQLite
        sqlite_cursor.execute('SELECT * FROM personas')
        personas = sqlite_cursor.fetchall()
        
        # Insertar en PostgreSQL
        for persona in personas:
            pg_cursor.execute('''
                INSERT INTO personas (
                    id, nombre, imagen, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    imagen = EXCLUDED.imagen,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at
            ''', (
                persona['id'], persona['nombre'], persona['imagen'],
                persona['created_at'], persona['updated_at']
            ))
        
        pg_conn.commit()
        print(f"Migradas {len(personas)} personas")
    except Exception as e:
        print(f"Error migrando personas: {e}")
        pg_conn.rollback()
        sys.exit(1)

def main():
    """Función principal"""
    print("Iniciando migración de datos de SQLite a PostgreSQL...")
    
    # Conectar a ambas bases de datos
    sqlite_conn = connect_sqlite()
    pg_conn = connect_postgres()
    
    try:
        # Crear tablas en PostgreSQL
        create_tables(pg_conn)
        
        # Migrar datos tabla por tabla
        migrate_users(sqlite_conn, pg_conn)
        migrate_sessions(sqlite_conn, pg_conn)
        migrate_verification_codes(sqlite_conn, pg_conn)
        migrate_photos(sqlite_conn, pg_conn)
        migrate_personas(sqlite_conn, pg_conn)
        
        print("¡Migración completada exitosamente!")
        
    except Exception as e:
        print(f"Error durante la migración: {e}")
    finally:
        # Cerrar conexiones
        sqlite_conn.close()
        pg_conn.close()
        print("Conexiones cerradas")

if __name__ == "__main__":
    main()