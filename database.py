import sqlite3

DB_NAME = 'memory.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS opt_outs (
            phone_number TEXT PRIMARY KEY
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone_number TEXT PRIMARY KEY,
            name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def set_user_name(phone_number: str, name: str):
    clean_name = name.strip()
    if not clean_name:
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (phone_number, name) VALUES (?, ?)
        ON CONFLICT(phone_number) DO UPDATE SET name = excluded.name
    ''', (phone_number, clean_name))
    conn.commit()
    conn.close()

def get_user_name(phone_number: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT name FROM users WHERE phone_number = ? LIMIT 1', (phone_number,))
    row = c.fetchone()
    conn.close()
    return row[0] if (row and row[0]) else None

def opt_out_user(phone_number: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO opt_outs (phone_number) VALUES (?)', (phone_number,))
    conn.commit()
    conn.close()

def opt_in_user(phone_number: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM opt_outs WHERE phone_number = ?', (phone_number,))
    conn.commit()
    conn.close()

def is_opted_out(phone_number: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT 1 FROM opt_outs WHERE phone_number = ?', (phone_number,))
    row = c.fetchone()
    conn.close()
    return row is not None

def has_user(phone_number: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT 1 FROM messages WHERE phone_number = ? LIMIT 1', (phone_number,))
    row = c.fetchone()
    if row:
        conn.close()
        return True
    c.execute('SELECT 1 FROM users WHERE phone_number = ? LIMIT 1', (phone_number,))
    row2 = c.fetchone()
    conn.close()
    return row2 is not None

def save_message(phone_number: str, role: str, content: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO messages (phone_number, role, content) VALUES (?, ?, ?)',
              (phone_number, role, content))
    conn.commit()
    conn.close()

def get_history(phone_number: str, limit: int = 6) -> str:
    """Returns a formatted string of the last N messages."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT role, content FROM messages 
        WHERE phone_number = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (phone_number, limit))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return "No prior history."
    
    # Reverse to chronological order
    history_lines = []
    for role, content in reversed(rows):
        history_lines.append(f"{role.capitalize()}: {content}")
        
    return "\n\n".join(history_lines)

def get_all_users() -> list[str]:
    """Returns all known phone numbers from both users and messages tables."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT phone_number FROM users
        UNION
        SELECT DISTINCT phone_number FROM messages
    ''')
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows if row[0]]

# Initialize on load
init_db()
