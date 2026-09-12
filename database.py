import sqlite3
import time

def get_db():
    return sqlite3.connect("misa_relations.db")

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей (баланс i¢)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 1000
        )
    """)
    
    # Таблица для браков (строго моногамные)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            user1_id INTEGER,
            user2_id INTEGER,
            PRIMARY KEY (user1_id, user2_id)
        )
    """)
    
    # Таблица для обычных отношений (с несколькими людьми, XP, таймером активности и последним действием)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            user1_id INTEGER,
            user2_id INTEGER,
            xp INTEGER DEFAULT 0,
            last_active INTEGER,
            last_action_time INTEGER DEFAULT 0,
            PRIMARY KEY (user1_id, user2_id)
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def get_user_balance(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, 1000)", (user_id,))
        conn.commit()
        balance = 1000
    else:
        balance = row[0]
    conn.close()
    return balance

def update_balance(user_id, amount):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- СИСТЕМА 13 УРОВНЕЙ ОТНОШЕНИЙ ---
def get_relationship_level(xp):
    levels_data = [
        (1, 0, "🌱 Незнакомцы"),
        (2, 100, "💬 Просто знакомые"),
        (3, 1000, "👀 Симпатия"),
        (4, 2000, "🤝 Близкие друзья"),
        (5, 3000, "💓 Тайная страсть"),
        (6, 5000, "🌹 Романтическая пара"),
        (7, 6000, "🔥 Пылающие чувства"),
        (8, 8000, "🧸 Неразлучники"),
        (9, 10000, "✨ Родная душа"),
        (10, 50000, "👑 Сердца воедино"),
        (11, 100000, "🌌 Космическая связь"),
        (12, 300000, "⚡ Вечная преданность"),
        (13, 500000, "💍 Истинные соулмейты"),
    ]
    
    current_lvl = 1
    current_title = "🌱 Незнакомцы"
    
    for lvl, req_xp, title in levels_data:
        if xp >= req_xp:
            current_lvl = lvl
            current_title = title
        else:
            break
            
    return current_lvl, current_title

def get_pair_xp(user1_id, user2_id):
    u1, u2 = min(user1_id, user2_id), max(user1_id, user2_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT xp FROM relations WHERE user1_id = ? AND user2_id = ?", (u1, u2))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def get_user_all_relations(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user1_id, user2_id, xp FROM relations 
        WHERE user1_id = ? OR user2_id = ?
        ORDER BY xp DESC
    """, (user_id, user_id))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- ДЕЙСТВИЯ (С КУЛДАУНАМИ) ---
def do_action(user1_id, user2_id, xp_gain, cost, cooldown_days=0, cooldown_seconds=60):
    if user1_id == user2_id:
        return False, "Нельзя выполнять действия с самим собой!"
    
    u1, u2 = min(user1_id, user2_id), max(user1_id, user2_id)
    now = int(time.time())
    
    total_cooldown = (cooldown_days * 24 * 60 * 60) if cooldown_days > 0 else cooldown_seconds
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT xp, last_action_time FROM relations WHERE user1_id = ? AND user2_id = ?", (u1, u2))
    row = cursor.fetchone()
    
    if row:
        last_action = row[1]
        time_passed = now - last_action
        if time_passed < total_cooldown:
            left_sec = total_cooldown - time_passed
            conn.close()
            
            if cooldown_days > 0:
                left_days = int(left_sec / (24 * 60 * 60)) + 1
                return False, f"⏳ Слишком рано! Такой подарок можно дарить этому человеку раз в 2 недели. Осталось примерно {left_days} дн."
            else:
                return False, f"⏳ Слишком часто! Повторить действие можно через {left_sec} сек."
            
    balance = get_user_balance(user1_id)
    if balance < cost:
        conn.close()
        return False, f"Недостаточно средств! Нужно {cost} i¢, а у вас на балансе {balance} i¢."
    
    update_balance(user1_id, -cost)
    
    if row:
        new_xp = row[0] + xp_gain
        cursor.execute("""
            UPDATE relations SET xp = ?, last_active = ?, last_action_time = ? WHERE user1_id = ? AND user2_id = ?
        """, (new_xp, now, now, u1, u2))
    else:
        cursor.execute("""
            INSERT INTO relations (user1_id, user2_id, xp, last_active, last_action_time) VALUES (?, ?, ?, ?, ?)
        """, (u1, u2, xp_gain, now, now))
        
    conn.commit()
    conn.close()
    
    new_balance = get_user_balance(user1_id)
    current_xp = get_pair_xp(user1_id, user2_id)
    lvl, title = get_relationship_level(current_xp)
    
    return True, f"Опыт отношений: +{xp_gain} (Всего: {current_xp} XP)\nРанг: {lvl} уровень — {title}\nСписано: {cost} i¢ (Остаток: {new_balance} i¢)"

# --- БРАКИ ---
def check_married(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM marriages WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def create_marriage(user1_id, user2_id):
    if user1_id == user2_id:
        return False, "Нельзя жениться на самом себе!"
    if check_married(user1_id) or check_married(user2_id):
        return False, "Кто-то из вас уже состоит в официальном браке! Сначала разберитесь со старыми узами."
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO marriages (user1_id, user2_id) VALUES (?, ?)", (user1_id, user2_id))
    conn.commit()
    conn.close()
    return True, "Поздравляем со свадьбой! 💍 Вы теперь официальные муж и жена."

def divorce_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM marriages WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
    conn.commit()
    conn.close()

def get_all_marriages():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user1_id, user2_id FROM marriages")
    rows = cursor.fetchall()
    conn.close()
    return rows