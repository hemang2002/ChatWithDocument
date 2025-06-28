# ChatWithDocument
This project is designed with a dual purpose: to help users understand the concepts of FIASS and to provide a practical tool for chatting with your documents. A key feature is its local execution, ensuring enhanced privacy as your data remains on your PC.

### Setup Instructions

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/hemang2002/ChatWithDocument.git
   cd ChatWithDocument

2. **Create a Virtual Environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate

3. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt

4. **Configure Environment (.env) Variables:**
     ```bash
   TAVILY_API_KEY = "Your/api/key"
   GROQ_API_KEY = "Your/api/key"
   LANGSMITH_API_KEY = "Your/api/key"
   DB_NAME = 'document_chat'
   DB_USER = 'user'
   DB_PASSWORD = 'password'
   DB_HOST = 'localhost'
   DB_PORT = '5432'

5. **Use Docker to run postgresSQL:**
     ```bash
     docker run --name postgres -e POSTGRES_USER="user" -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres

6. **Use Docker to run Redis Server:**      
      ```bash
      docker run -d -p 6379:6379 -p 8001:8001 redis/redis-stack:latest

7. **Run app.py:**
   ```bash
   python app.py
   
Project is under development......
