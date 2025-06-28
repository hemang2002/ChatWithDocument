import os
import logging
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, make_response
from flask_cors import CORS
from langchain_core.runnables.utils import Output
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
import bleach
import psycopg2
from celery import Celery
import uuid
import bcrypt
import re
from datetime import datetime, timedelta
import jwt
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from src.indexers import FAISSVectorStore
from src.chunking import RAGChunker
from src.generator import ChatDocs
from langchain_huggingface import HuggingFaceEmbeddings
import PyPDF2
import docx
from Configuration import config
from modules.database import init_db, create_user, get_user_by_email, create_chat_db, get_chats_db, delete_chat_db, verify_otp, get_db_connection, connection_pool
from modules.redis_client import RedisClient
from modules.tasks import index_document_task, send_otp_task

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app, supports_credentials=True)
csrf = CSRFProtect(app)

# Rate limiting
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0' if os.environ.get('FLASK_ENV', 'development') == 'development' else 'redis://redis:6379/0')
limiter = Limiter(app, storage_uri=redis_url, default_limits=["200 per day", "50 per hour"])

# Configuration
app.config['SECRET_KEY'] = config.SECRET_KEY or os.urandom(24).hex()
app.config['JWT_COOKIE_NAME'] = config.JWT_COOKIE_NAME
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB file size limit
app.config['CELERY_BROKER_URL'] = os.environ.get('CELERY_BROKER_URL', redis_url)
app.config['CELERY_RESULT_BACKEND'] = os.environ.get('CELERY_RESULT_BACKEND', redis_url)
app.config['FLASK_ENV'] = os.environ.get('FLASK_ENV', 'development')

# Initialize database
init_db()

# Celery configuration
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_RESULT_BACKEND'])
celery.conf.update(app.config)

# Initialize components
UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

redis_client = RedisClient()
embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
chunker = RAGChunker(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    use_semantic_chunking=config.USER_SEMANTIC_CHUNKING,
    embeddings=embeddings
)
vector_store = FAISSVectorStore(
    index_path=config.INDEX_PATH,
    use_semantic_chunking=config.USER_SEMANTIC_CHUNKING,
    chunker=chunker,
    embeddings=embeddings
)
rag_system = ChatDocs(
    llm_model=config.LLM_MODEL,
    similarity_threshold=config.SIMILARITY_THRESHOLD,
    use_semantic_chunking=config.USER_SEMANTIC_CHUNKING,
    vector_store=vector_store,
    embeddings=embeddings
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_file_size(bytes):
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1048576:
        return f"{bytes / 1024:.1f} KB"
    else:
        return f"{bytes / 1048576:.1f} MB"

def extract_text_from_file(file_path, extension):
    try:
        if extension == 'pdf':
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ''
                for page in pdf_reader.pages:
                    text += page.extract_text() or ''
                return text
        elif extension == 'docx':
            doc = docx.Document(file_path)
            return '\n'.join([para.text for para in doc.paragraphs])
        elif extension == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            return ''
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {str(e)}")
        return ''

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if app.config['JWT_COOKIE_NAME'] in request.cookies:
            token = request.cookies.get(app.config['JWT_COOKIE_NAME'])
        elif 'Authorization' in request.headers:
            auth_header = request.headers.get('Authorization')
            if auth_header.startswith('Bearer'):
                token = auth_header.split(' ')[1]

        if not token:
            logger.warning("Token missing in request")
            return jsonify({'error': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
            current_user_name = data['user_name']
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return jsonify({'error': 'Invalid token'}), 401

        return f(current_user_id, current_user_name, *args, **kwargs)
    return decorated

@app.before_request
def enforce_https():
    if not request.is_secure and app.config['FLASK_ENV'] == 'production':
        return redirect(request.url.replace('http://', 'https://'), code=301)

@app.route('/')
def index():
    token = request.cookies.get(app.config['JWT_COOKIE_NAME'])
    if not token:
        return redirect(url_for('login'))
    try:
        jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return render_template('index.html')
    except jwt.InvalidTokenError:
        return redirect(url_for('login'))

@app.route('/login')
def login():
    token = request.cookies.get(app.config['JWT_COOKIE_NAME'])
    if token:
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return redirect(url_for('index'))
        except jwt.InvalidTokenError:
            pass
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
@csrf.exempt
def api_login():
    data = request.get_json()
    email = bleach.clean(data.get('email', ''))
    password = data.get('password', '')

    if not email or not password:
        logger.warning("Login attempt with missing email or password")
        return jsonify({'error': 'Email and password are required'}), 400

    cache_key = f"user:email:{email}"
    cached_user = redis_client.get_cache(cache_key)
    
    if cached_user:
        user = cached_user
    else:
        user = get_user_by_email(email)
        if user:
            redis_client.set_cache(cache_key, user)

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        token = jwt.encode({
            'user_id': user['id'],
            'user_name': user['user_name'],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        response = make_response(jsonify({'message': 'Login successful'}), 200)
        response.set_cookie(
            app.config['JWT_COOKIE_NAME'],
            token,
            httponly=True,
            secure=app.config['FLASK_ENV'] == 'production',
            samesite='Strict',
            expires=datetime.utcnow() + timedelta(hours=24)
        )
        logger.info(f"User {email} logged in successfully")
        return response
    else:
        logger.warning(f"Failed login attempt for {email}")
        return jsonify({'error': 'Invalid email or password'}), 401

@app.route('/api/signup', methods=['POST'])
@limiter.limit("5 per minute")
@csrf.exempt
def api_signup():
    data = request.get_json()
    user_name = bleach.clean(data.get('userName', ''))
    email = bleach.clean(data.get('email', ''))
    phone = bleach.clean(data.get('phone', ''))
    organization = bleach.clean(data.get('organization', ''))
    password = data.get('password', '')

    if not user_name or not email or not phone or not password:
        logger.warning("Signup attempt with missing fields")
        return jsonify({'error': 'All fields are required'}), 400

    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        logger.warning(f"Invalid email format: {email}")
        return jsonify({'error': 'Invalid email format'}), 400

    phone_regex = r'^[0-9]{10}$'
    if not re.match(phone_regex, phone):
        logger.warning(f"Invalid phone number format: {phone}")
        return jsonify({'error': 'Invalid phone number format'}), 400

    user_id = create_user(user_name, email, password, organization, phone)
    if user_id:
        token = jwt.encode({
            'user_id': user_id,
            'user_name': user_name,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        response = make_response(jsonify({'message': 'Account created successfully'}), 201)
        response.set_cookie(
            app.config['JWT_COOKIE_NAME'],
            token,
            httponly=True,
            secure=app.config['FLASK_ENV'] == 'production',
            samesite='Strict',
            expires=datetime.utcnow() + timedelta(hours=24)
        )
        redis_client.delete_cache(f"user:email:{email}")
        logger.info(f"User {email} signed up successfully")
        return response
    else:
        logger.warning(f"Signup failed: Email {email} already exists")
        return jsonify({'error': 'Email already exists'}), 400

@app.route('/api/logout', methods=['POST'])
@csrf.exempt
def logout():
    response = make_response(jsonify({'message': 'Logged out successfully'}), 200)
    response.set_cookie(
        app.config['JWT_COOKIE_NAME'],
        '',
        httponly=True,
        secure=app.config['FLASK_ENV'] == 'production',
        samesite='Strict',
        expires=0
    )
    logger.info("User logged out")
    return response

@app.route('/api/check-auth', methods=['GET'])
@limiter.limit("10 per minute")
def check_auth():
    token = request.cookies.get(app.config['JWT_COOKIE_NAME'])
    if token:
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return jsonify({'authenticated': True}), 200
        except jwt.InvalidTokenError:
            logger.warning("Check-auth failed: Invalid token")
            return jsonify({'authenticated': False}), 401
    logger.warning("Check-auth failed: No token")
    return jsonify({'authenticated': False}), 401

@app.route('/api/send-otp', methods=['POST'])
@limiter.limit("5 per minute")
@csrf.exempt
def send_otp_route():
    data = request.get_json()
    email = bleach.clean(data.get('email', ''))
    phone = bleach.clean(data.get('phone', ''))

    if not email or not phone:
        logger.warning("Send OTP attempt with missing email or phone")
        return jsonify({'error': 'Email and phone are required'}), 400

    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        logger.warning(f"Invalid email format for OTP: {email}")
        return jsonify({'error': 'Invalid email format'}), 400

    phone_regex = r'^[0-9]{10}$'
    if not re.match(phone_regex, phone):
        logger.warning(f"Invalid phone number format for OTP: {phone}")
        return jsonify({'error': 'Invalid phone number format'}), 400

    send_otp_task.delay(email, phone)
    logger.info(f"OTP sent for {email}/{phone}")
    return jsonify({'message': 'OTP sent successfully'}), 200

@app.route('/api/verify-email-otp', methods=['POST'])
@limiter.limit("10 per minute")
@csrf.exempt
def verify_email_otp():
    data = request.get_json()
    email = bleach.clean(data.get('email', ''))
    otp = bleach.clean(data.get('otp', ''))

    if not email or not otp:
        logger.warning("Verify email OTP attempt with missing fields")
        return jsonify({'error': 'Email and OTP are required'}), 400

    if verify_otp(email, None, otp):
        logger.info(f"Email OTP verified for {email}")
        return jsonify({'message': 'Email OTP verified successfully'}), 200
    else:
        logger.warning(f"Invalid email OTP for {email}")
        return jsonify({'error': 'Invalid OTP'}), 400

@app.route('/api/verify-phone-otp', methods=['POST'])
@limiter.limit("10 per minute")
@csrf.exempt
def verify_phone_otp():
    data = request.get_json()
    phone = bleach.clean(data.get('phone', ''))
    otp = bleach.clean(data.get('otp', ''))

    if not phone or not otp:
        logger.warning("Verify phone OTP attempt with missing fields")
        return jsonify({'error': 'Phone and OTP are required'}), 400

    if verify_otp(None, phone, otp):
        logger.info(f"Phone OTP verified for {phone}")
        return jsonify({'message': 'Phone OTP verified successfully'}), 200
    else:
        logger.warning(f"Invalid phone OTP for {phone}")
        return jsonify({'error': 'Invalid OTP'}), 400

@app.route('/api/upload', methods=['POST'])
@token_required
# @limiter.limit("10 per minute")
@csrf.exempt
def upload_document(current_user_id, current_user_name):
    try:
        if 'file' not in request.files:
            logger.warning(f"Upload attempt by {current_user_id} with no file")
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            logger.warning(f"Upload attempt by {current_user_id} with no file selected")
            return jsonify({'error': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            chat_id = bleach.clean(request.form.get('chat_id', '')) 
            if not chat_id:
                logger.warning(f"Upload attempt by {current_user_id} with no chat ID")
                return jsonify({'error': 'No chat ID provided'}), 400

            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()  # Fixed split to handle filenames correctly
            file_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.{file_ext}")
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            upload_date = datetime.now()

            if file_ext == 'pdf':
                try:
                    with open(file_path, 'rb') as f:
                        PyPDF2.PdfReader(f)
                except Exception as e:
                    os.remove(file_path)
                    logger.error(f"Invalid PDF uploaded by {current_user_id}: {str(e)}")
                    return jsonify({'error': 'Invalid PDF file'}), 400

            conn = get_db_connection()
            try:
                c = conn.cursor()
                c.execute('SELECT filename FROM documents WHERE chat_id = %s AND filename = %s AND extension = %s',
                          (chat_id, filename, file_ext))
                existing_file = c.fetchone()
                if existing_file:
                    os.remove(file_path)
                    logger.warning(f"Duplicate file upload attempt by {current_user_id}: {filename}")
                    return jsonify({'error': 'File already exists'}), 400

                c.execute('''
                    INSERT INTO documents (id, filename, size, upload_date, extension, chat_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (file_id, filename, file_size, upload_date, file_ext, chat_id))
                conn.commit()
            except Exception as e:
                conn.rollback()
                os.remove(file_path)
                logger.error(f"Database error during document upload by {current_user_id}: {str(e)}")
                return jsonify({'error': 'Database error'}), 500
            finally:
                if conn:
                    connection_pool.putconn(conn)

            text = extract_text_from_file(file_path, file_ext)
            print(text)
            if not text:
                os.remove(file_path)
                logger.error(f"Failed to extract text from {filename} by {current_user_id}")
                return jsonify({'error': 'Unable to extract text from file'}), 400

            try:
                index_document_task(file_id, text, chat_id, filename, f"{file_id}.{file_ext}")
            except Exception as e:
                logger.error(f"Error scheduling index task for {file_id}: {str(e)}")

            redis_client.delete_cache(f"documents:chat:{chat_id}")
            logger.info(f"Document {filename} uploaded by {current_user_id}")
            return jsonify({
                'id': file_id,
                'filename': filename,
                'size': format_file_size(file_size),
                'upload_date': upload_date.strftime('%B %d, %Y'),
                'extension': file_ext,
                'chat_id': chat_id
            }), 200
        logger.warning(f"Invalid file type uploaded by {current_user_id}: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400
    except RequestEntityTooLarge:
        logger.warning(f"File too large uploaded by {current_user_id}")
        return jsonify({'error': 'File size exceeds 16MB limit'}), 413

@app.route('/api/documents', methods=['GET'])
@token_required
@limiter.limit("20 per minute")
def get_documents(current_user_id, current_user_name):
    chat_id = bleach.clean(request.args.get('chat_id', '')) 
    if not chat_id:
        logger.warning(f"Get documents retrieval attempt by {current_user_id}")
        return jsonify({'error': 'No chat ID provided'}), 400

    cache_key = f"documents:chat:{chat_id}"
    cached_documents = redis_client.get_cache(cache_key)
    
    if cached_documents:
        return jsonify(cached_documents), 200

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            SELECT id, filename, size, upload_date, extension 
            FROM documents 
            WHERE chat_id = %s 
            ORDER BY upload_date DESC
        ''', (chat_id,))
        documents = c.fetchall()
        
        formatted_documents = [{
            'id': doc[0],
            'filename': doc[1],
            'size': format_file_size(doc[2]),
            'upload_date': doc[3].strftime('%B %d, %Y'),
            'extension': doc[4]
        } for doc in documents]

        redis_client.set_cache(cache_key, formatted_documents)
        logger.info(f"Retrieved documents for chat {chat_id} by {current_user_id}")
        return jsonify(formatted_documents), 200
    except psycopg2.Error as e:
        logger.error(f"Error retrieving documents for chat {chat_id}: {str(e)}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/api/documents/<id>', methods=['DELETE'])
@token_required
@limiter.limit("10 per minute")
@csrf.exempt
def delete_document(current_user_id, current_user_name, id):
    id = bleach.clean(id)
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT extension, chat_id FROM documents WHERE id = %s', (id,))
        document = c.fetchone()

        if not document:
            logger.warning(f"Document {id} not found for deletion by {current_user_id}")
            return jsonify({'message': 'Document not found'}), 404

        extension, chat_id = document
        file_path = os.path.join(UPLOAD_FOLDER, f"{id}.{extension}")

        try:
            vector_store.delete_documents([id])
        except Exception as e:
            logger.error(f"Error deleting document {id} from vector store: {str(e)}")
            return jsonify({'error': 'Failed to delete document from vector store'}), 500

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            return jsonify({'error': 'Failed to delete file'}), 500

        c.execute('DELETE FROM documents WHERE id = %s', (id,))
        conn.commit()

        redis_client.delete_cache(f"documents:chat:{chat_id}")
        redis_client.delete_cache(f"document:{id}")
        logger.info(f"Document {id} deleted by {current_user_id}")
        return jsonify({'message': 'Document deleted successfully'}), 200
    except psycopg2.Error as e:
        logger.error(f"Error deleting document {id}: {str(e)}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/api/chats', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
@csrf.exempt
def create_chat(current_user_id, current_user_name):
    title = f'Chat {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    try:
        chat_id, title, created_at = create_chat_db(current_user_id, title)
        redis_client.delete_cache(f"chats:user:{current_user_id}")
        logger.info(f"Chat {chat_id} created by {current_user_id}")
        return jsonify({'id': chat_id, 'title': title, 'created_at': created_at}), 200
    except Exception as e:
        logger.error(f"Error creating chat for user {current_user_id}: {str(e)}")
        return jsonify({'error': 'Failed to create chat'}), 500

@app.route('/api/chats', methods=['GET'])
@token_required
@limiter.limit("20 per minute")
def get_chats(current_user_id, current_user_name):
    cache_key = f"chats:user:{current_user_id}"
    cached_chats = redis_client.get_cache(cache_key)
    
    if cached_chats:
        return jsonify(cached_chats), 200

    chats = get_chats_db(current_user_id)
    redis_client.set_cache(cache_key, chats)
    logger.info(f"Retrieved chats for {current_user_id}")
    return jsonify(chats), 200

@app.route('/api/chats/<id>', methods=['DELETE'])
@token_required
@limiter.limit("10 per minute")
@csrf.exempt
def delete_chat(current_user_id, current_user_name, id):
    id = bleach.clean(id)
    success, message = delete_chat_db(id, current_user_id)
    
    if success:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('SELECT id FROM documents WHERE chat_id = %s', (id,))
            doc_ids = [doc[0] for doc in c.fetchall()]
            if doc_ids:
                vector_store.delete_documents(doc_ids)
        except Exception as e:
            logger.error(f"Error deleting documents for chat {id}: {str(e)}")
            return jsonify({'error': 'Failed to delete documents from vector store'}), 500
        finally:
            if conn:
                connection_pool.putconn(conn)

        redis_client.delete_cache(f"chats:user:{current_user_id}")
        redis_client.delete_cache(f"documents:chat:{id}")
        redis_client.delete_cache(f"messages:chat:{id}")
        for doc_id in doc_ids:
            redis_client.delete_cache(f"document:{doc_id}")
        logger.info(f"Chat {id} deleted by {current_user_id}")
        return jsonify({'message': message}), 200
    else:
        logger.warning(f"Chat deletion failed for {id} by {current_user_id}: {message}")
        return jsonify({'error': message}), 400

@app.route('/api/chats/<chat_id>/messages', methods=['POST'])
@token_required
@limiter.limit("20 per minute")
@csrf.exempt
def send_message(current_user_id, current_user_name, chat_id):
    message_content = request.json.get('content')
    if not message_content:
        logger.warning(f"Message send attempt by {current_user_id} with no content")
        return jsonify({'error': 'Message content is required'}), 400
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT id FROM chats WHERE id = %s AND user_id = %s', (chat_id, current_user_id))
        if not c.fetchone():
            conn.close()
            logger.warning(f"Chat {chat_id} not found or access denied for {current_user_id}")
            return jsonify({'error': 'Chat not found or access denied'}), 404
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
        INSERT INTO messages (id, chat_id, content, sender, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        ''', (message_id, chat_id, message_content, 'user', timestamp))
        rag_system.find_content(message_content, chat_id = chat_id)  # Pass chat_id to filter documents
        bot_response = rag_system.run()
        bot_message_id = str(uuid.uuid4())
        c.execute('''
        INSERT INTO messages (id, chat_id, content, sender, timestamp)
        VALUES (%s, %s, %s, %s, %s)
        ''', (bot_message_id, chat_id, bot_response, 'bot', timestamp))
        Output = {
            'user_message': {
                'id': message_id,
                'content': message_content,
                'sender': 'user',
                'timestamp': timestamp
            },
            'bot_response': {
                'id': bot_message_id,
                'content': bot_response,
                'sender': 'bot',
                'timestamp': timestamp
            }
        }
        conn.commit()
        conn.close()
        redis_client.delete_cache(f"messages:chat:{chat_id}")
        return jsonify(Output), 200
    except Exception as e:
        logger.error(f"Error generating bot response: {e}")
        bot_response = "Sorry, I couldn't process your request at this time."
        message_id = str(uuid.uuid4())
        bot_message_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        Output = {
            'user_message': {
                'id': message_id,
                'content': message_content,
                'sender': 'user',
                'timestamp': timestamp
            },
            'bot_response': {
                'id': bot_message_id,
                'content': bot_response,
                'sender': 'bot',
                'timestamp': timestamp
            }
        }
        return jsonify(Output), 500
        

@app.route('/api/chats/<chat_id>/messages', methods=['GET'])
@token_required
@limiter.limit("20 per minute")
def get_messages(current_user_id, current_user_name, chat_id):
    chat_id = bleach.clean(chat_id)
    cache_key = f"messages:chat:{chat_id}"
    cached_messages = redis_client.get_cache(cache_key)
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id FROM chats WHERE id = %s AND user_id = %s', (chat_id, current_user_id))
        chat = c.fetchone()
        if not chat:
            logger.warning(f"Messages request for chat {chat_id} not found or access denied for {current_user_id}")
            return jsonify({'error': 'Chat not found or access denied'}), 404

        c.execute('''
            SELECT id, content, sender, timestamp
            FROM messages
            WHERE chat_id = %s
            ORDER BY timestamp
        ''', (chat_id,))
        messages = c.fetchall()

        formatted_messages = [{
            'id': msg[0],
            'content': msg[1],
            'sender': msg[2],
            'timestamp': msg[3].strftime('%Y-%m-%d %H:%M:%S')
        } for msg in messages]

        redis_client.set_cache(cache_key, formatted_messages)
        logger.info(f"Retrieved messages for chat {chat_id} by {current_user_id}")
        return jsonify(formatted_messages), 200
    except psycopg2.Error as e:
        logger.error(f"Error retrieving messages for chat {chat_id}: {str(e)}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/api/account-settings', methods=['GET'])
@token_required
@limiter.limit("10 per minute")
def get_account_settings(current_user_id, current_user_name):
    cache_key = f"user:settings:{current_user_id}"
    cached_settings = redis_client.get_cache(cache_key)
    
    if cached_settings:
        return jsonify(cached_settings), 200

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id, user_name, email, organization_name, phone_number FROM users WHERE id = %s', (current_user_id,))
        user = c.fetchone()

        if user:
            settings = {
                'id': user[0],
                'user_name': user[1],
                'email': user[2],
                'organization_name': user[3],
                'phone_number': user[4]
            }
            redis_client.set_cache(cache_key, settings)
            logger.info(f"Retrieved account settings for {current_user_id}")
            return jsonify(settings), 200
        else:
            logger.warning(f"User {current_user_id} not found for account settings")
            return jsonify({'error': 'User not found'}), 404
    except psycopg2.Error as e:
        logger.error(f"Error retrieving settings for user {current_user_id}: {str(e)}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/api/account-settings', methods=['POST'])
@token_required
@limiter.limit("5 per minute")
@csrf.exempt
def save_account_settings(current_user_id, current_user_name):
    data = request.get_json()
    user_name = bleach.clean(data.get('userName', ''))
    organization_name = bleach.clean(data.get('organizationName', ''))
    phone_number = bleach.clean(data.get('phoneNumber', ''))
    email = bleach.clean(data.get('email', ''))

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            UPDATE users
            SET user_name = %s, organization_name = %s, phone_number = %s, email = %s
            WHERE id = %s
        ''', (user_name, organization_name, phone_number, email, current_user_id))
        conn.commit()

        redis_client.delete_cache(f"user:settings:{current_user_id}")
        redis_client.delete_cache(f"user:email:{email}")

        token = jwt.encode({
            'user_id': current_user_id,
            'user_name': user_name,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        response = make_response(jsonify({'message': 'Account settings updated successfully'}), 200)
        response.set_cookie(
            app.config['JWT_COOKIE_NAME'],
            token,
            httponly=True,
            secure=app.config['FLASK_ENV'] == 'production',
            samesite='Strict',
            expires=datetime.utcnow() + timedelta(hours=24)
        )
        logger.info(f"Account settings updated for {current_user_id}")
        return response
    except psycopg2.Error as e:
        logger.error(f"Error updating account settings for {current_user_id}: {str(e)}")
        conn.rollback()
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/api/documents/<id>', methods=['GET'])
@token_required
@limiter.limit("20 per minute")
def download_document(current_user_id, current_user_name, id):
    id = bleach.clean(id)
    cache_key = f"document:{id}"
    cached_document = redis_client.get_cache(cache_key)
    
    if cached_document:
        filename, extension = cached_document['filename'], cached_document['extension']
    else:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('SELECT filename, extension FROM documents WHERE id = %s', (id,))
            document = c.fetchone()
            if not document:
                logger.warning(f"Document {id} not found for download by {current_user_id}")
                return jsonify({'error': 'Document not found'}), 404
            filename, extension = document
            redis_client.set_cache(cache_key, {'filename': filename, 'extension': extension})
        except psycopg2.Error as e:
            logger.error(f"Error retrieving document {id}: {str(e)}")
            return jsonify({'error': 'Database error'}), 500
        finally:
            if conn:
                connection_pool.putconn(conn)

    file_path = os.path.join(UPLOAD_FOLDER, f"{id}.{extension}")
    if not os.path.exists(file_path):
        logger.warning(f"File {file_path} not found for download by {current_user_id}")
        return jsonify({'error': 'File not found'}), 404

    logger.info(f"Document {id} downloaded by {current_user_id}")
    return send_from_directory(UPLOAD_FOLDER, f"{id}.{extension}", as_attachment=False)

@app.route('/api/chats', methods=['DELETE'])
@token_required
@limiter.limit("5 per minute")
@csrf.exempt
def delete_all_chats(current_user_id, current_user_name):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id FROM chats WHERE user_id = %s', (current_user_id,))
        chats = c.fetchall()
        chat_ids = [chat[0] for chat in chats]

        for chat_id in chat_ids:
            c.execute('SELECT id, extension FROM documents WHERE chat_id = %s', (chat_id,))
            documents = c.fetchall()
            doc_ids = [doc[0] for doc in documents]
            for doc in documents:
                file_path = os.path.join(UPLOAD_FOLDER, f"{doc[0]}.{doc[1]}")
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {str(e)}")
            if doc_ids:
                try:
                    vector_store.delete_documents(doc_ids)
                except Exception as e:
                    logger.error(f"Error deleting documents for chat {chat_id}: {str(e)}")
                    return jsonify({'error': 'Failed to delete documents from vector store'}), 500

        c.execute('DELETE FROM chats WHERE user_id = %s', (current_user_id,))
        conn.commit()

        redis_client.delete_cache(f"chats:user:{current_user_id}")
        for chat_id in chat_ids:
            redis_client.delete_cache(f"documents:chat:{chat_id}")
            redis_client.delete_cache(f"messages:chat:{chat_id}")
        logger.info(f"All chats deleted for {current_user_id}")
        return jsonify({'message': 'All chats deleted successfully'}), 200
    except psycopg2.Error as e:
        logger.error(f"Error deleting all chats for {current_user_id}: {str(e)}")
        conn.rollback()
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/api/account', methods=['DELETE'])
@token_required
@limiter.limit("5 per minute")
@csrf.exempt
def delete_account(current_user_id, current_user_name):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT email FROM users WHERE id = %s', (current_user_id,))
        user = c.fetchone()
        
        c.execute('SELECT id FROM chats WHERE user_id = %s', (current_user_id,))
        chats = c.fetchall()
        chat_ids = [chat[0] for chat in chats]
        for chat_id in chat_ids:
            c.execute('SELECT id FROM documents WHERE chat_id = %s', (chat_id,))
            documents = c.fetchall()
            doc_ids = [doc[0] for doc in documents]
            if doc_ids:
                try:
                    vector_store.delete_documents(doc_ids)
                except Exception as e:
                    logger.error(f"Error deleting documents for user {current_user_id}: {str(e)}")
                    return jsonify({'error': 'Failed to delete documents from vector store'}), 500

        c.execute('DELETE FROM users WHERE id = %s', (current_user_id,))
        conn.commit()

        redis_client.delete_cache(f"user:settings:{current_user_id}")
        if user:
            redis_client.delete_cache(f"user:email:{user[0]}")
        redis_client.delete_cache(f"chats:user:{current_user_id}")
        for chat_id in chat_ids:
            redis_client.delete_cache(f"documents:chat:{chat_id}")
            redis_client.delete_cache(f"messages:chat:{chat_id}")

        response = make_response(jsonify({'message': 'Account deleted successfully'}), 200)
        response.set_cookie(
            app.config['JWT_COOKIE_NAME'],
            '',
            httponly=True,
            secure=app.config['FLASK_ENV'] == 'production',
            samesite='Strict',
            expires=0
        )
        logger.info(f"Account deleted for {current_user_id}")
        return response
    except psycopg2.Error as e:
        logger.error(f"Error deleting account for {current_user_id}: {str(e)}")
        conn.rollback()
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

@app.route('/health')
def health():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT 1')
        redis_client.client.ping()
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy'}), 500
    finally:
        if conn:
            connection_pool.putconn(conn)

if __name__ == '__main__':
    app.run(debug=True)#, host='0.0.0.0', port=5000)