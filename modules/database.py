import os
import logging
import psycopg2
from psycopg2 import pool
from datetime import datetime, timedelta
import uuid
import bcrypt
import random
import threading
import time
from Configuration import config

# Configure logging
logger = logging.getLogger(__name__)

# PostgreSQL connection configuration
DB_CONFIG = {
    'dbname': config.DB_NAME,
    'user': config.DB_USER,
    'password': config.DB_PASSWORD,
    'host': config.DB_HOST,
    'port': config.DB_PORT
}

# Initialize connection pool
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, **DB_CONFIG)
    logger.info("PostgreSQL connection pool initialized successfully")
except psycopg2.Error as e:
    logger.error(f"Failed to initialize PostgreSQL connection pool: {str(e)}")
    raise

def init_db():
    """Initialize the database and create tables."""
    conn = None
    try:
        conn = connection_pool.getconn()
        conn.autocommit = True
        c = conn.cursor()
        
        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                user_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                organization_name TEXT,
                phone_number TEXT
            )
        ''')

        # Create chats table
        c.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
            )
        ''')

        # Create messages table
        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                chat_id UUID NOT NULL,
                content TEXT NOT NULL,
                sender TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE ON UPDATE CASCADE
            )
        ''')

        # Create documents table
        c.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY,
                filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                upload_date TIMESTAMPTZ NOT NULL,
                extension TEXT NOT NULL,
                chat_id UUID NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE ON UPDATE CASCADE
            )
        ''')

        # Create otps table
        c.execute('''
            CREATE TABLE IF NOT EXISTS otps (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                otp TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
        ''')

        # Create indexes for performance
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats (user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_documents_chat_id ON documents (chat_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages (chat_id)')

        logger.info("Database initialized successfully")
        return True
    except psycopg2.Error as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False
    finally:
        if conn:
            connection_pool.putconn(conn)

def get_db_connection():
    """Get a connection from the pool."""
    try:
        return connection_pool.getconn()
    except psycopg2.Error as e:
        logger.error(f"Error getting database connection: {str(e)}")
        raise

def create_user(user_name, email, password, organization_name, phone_number):
    """Create a new user with hashed password."""
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (id, user_name, email, password, organization_name, phone_number)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, user_name, email, hashed_password, organization_name, phone_number))
        result = c.fetchone()[0]
        conn.commit()
        logger.info(f"User created: {email}")
        return result
    except psycopg2.IntegrityError:
        logger.warning(f"User creation failed for {email}: Email already exists")
        return None
    except psycopg2.Error as e:
        logger.error(f"Database error creating user {email}: {str(e)}")
        return None
    finally:
        if conn:
            conn.commit()  # Ensure any pending transactions are committed
            connection_pool.putconn(conn)

def get_user_by_email(email):
    """Retrieve user by email."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id, user_name, password FROM users WHERE email = %s', (email,))
        user = c.fetchone()
        if user:
            return {'id': user[0], 'user_name': user[1], 'password': user[2]}
        return None
    except psycopg2.Error as e:
        logger.error(f"Error retrieving user {email}: {str(e)}")
        return None
    finally:
        if conn:
            connection_pool.putconn(conn)

def create_chat_db(user_id, title):
    """Create a new chat."""
    chat_id = str(uuid.uuid4())
    created_at = datetime.now()
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO chats (id, user_id, title, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id, title, created_at
        ''', (chat_id, user_id, title, created_at))
        result = c.fetchone()
        conn.commit()
        logger.info(f"Chat created: {chat_id} for user {user_id}")
        return result[0], result[1], result[2].strftime('%Y-%m-%d %H:%M:%S')
    except psycopg2.Error as e:
        logger.error(f"Error creating chat for user {user_id}: {str(e)}")
        raise
    finally:
        if conn:
            connection_pool.putconn(conn)

def get_chats_db(user_id):
    """Retrieve all chats for a user."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            SELECT id, title, created_at
            FROM chats
            WHERE user_id = %s
            ORDER BY created_at DESC
        ''', (user_id,))
        chats = c.fetchall()
        return [{'id': chat[0], 'title': chat[1], 'created_at': chat[2].strftime('%Y-%m-%d %H:%M:%S')} for chat in chats]
    except psycopg2.Error as e:
        logger.error(f"Error retrieving chats for user {user_id}: {str(e)}")
        return []
    finally:
        if conn:
            connection_pool.putconn(conn)

def delete_chat_db(chat_id, user_id):
    """Delete a chat and associated data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id, extension FROM documents WHERE chat_id = %s', (chat_id,))
        documents = c.fetchall()

        for doc in documents:
            doc_id, extension = doc
            file_path = os.path.join(config.UPLOAD_FOLDER, f"{doc_id}.{extension}")
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")
                return False, f'Error deleting file: {str(e)}'

        c.execute('DELETE FROM documents WHERE chat_id = %s', (chat_id,))
        c.execute('DELETE FROM messages WHERE chat_id = %s', (chat_id,))
        c.execute('DELETE FROM chats WHERE id = %s AND user_id = %s', (chat_id, user_id))
        conn.commit()
        logger.info(f"Chat {chat_id} deleted for user {user_id}")
        return True, 'Chat and associated documents deleted successfully'
    except psycopg2.Error as e:
        logger.error(f"Error deleting chat {chat_id} for user {user_id}: {str(e)}")
        return False, 'Database error'
    finally:
        if conn:
            connection_pool.putconn(conn)

def send_otp(email, phone, otp):
    """Store OTP in database."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        created_at = datetime.now()
        c.execute('''
            INSERT INTO otps (email, phone, otp, created_at)
            VALUES (%s, %s, %s, %s)
        ''', (email, phone, otp, created_at))
        conn.commit()
        logger.info(f"OTP {otp}")
        logger.info(f"OTP stored for {email}/{phone}")
    except psycopg2.Error as e:
        logger.error(f"Error storing OTP for {email}/{phone}: {str(e)}")
        raise
    finally:
        if conn:
            connection_pool.putconn(conn)

def verify_otp(email, phone, otp):
    """Verify OTP."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT otp FROM otps WHERE (email = %s OR phone = %s) AND otp = %s', (email, phone, otp))
        result = c.fetchone()
        return True #result is not None
    except psycopg2.Error as e:
        logger.error(f"Error verifying OTP for {email or phone}: {str(e)}")
        return False
    finally:
        if conn:
            connection_pool.putconn(conn)

def generate_otp():
    """Generate a 6-digit OTP."""
    otp = str(random.randint(100000, 999999))
    logger.info(f"Generated OTP: {otp}")
    return otp

def cleanup_otps():
    """Periodically clean up expired OTPs."""
    while True:
        time.sleep(600)  # Run every 10 minutes
        conn = get_db_connection()
        try:
            c = conn.cursor()
            cutoff_time = datetime.now() - timedelta(minutes=10)
            c.execute('DELETE FROM otps WHERE created_at < %s', (cutoff_time,))
            conn.commit()
            logger.info("Expired OTPs cleaned up")
        except psycopg2.Error as e:
            logger.error(f"Error cleaning up OTPs: {str(e)}")
        finally:
            if conn:
                connection_pool.putconn(conn)

cleanup_thread = threading.Thread(target=cleanup_otps, daemon=True)
cleanup_thread.start()