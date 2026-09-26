import aiosqlite

DB = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT DEFAULT '',
                nick_bot TEXT DEFAULT '',
                nick_server TEXT DEFAULT '',
                fraction TEXT DEFAULT '',
                uuid TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS globals (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS factions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT UNIQUE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS images (
                key TEXT PRIMARY KEY,
                file_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS resourcepack (
                key TEXT PRIMARY KEY,
                file_id TEXT,
                instruction TEXT
            )
        """)
        await db.commit()

        # --- МИГРАЦИИ: добавляем колонки, если их ещё нет ---
        await _ensure_column(db, "users", "first_name", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "nick_bot", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "nick_server", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "fraction", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "uuid", "TEXT DEFAULT ''")


async def _ensure_column(db, table: str, column: str, coltype: str):
    """Если колонки нет — добавляет её. Если есть — ничего не делает."""
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        cols = [row[1] for row in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        await db.commit()


# ---------- Пользователи ----------
async def get_user(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT user_id, username, nick_bot, nick_server, fraction, uuid "
            "FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            return await cur.fetchone()

async def add_user(user_id: int, username: str, first_name: str = ""):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)) as cur:
            exists = await cur.fetchone()
        if not exists:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, nick_bot) "
                "VALUES (?, ?, ?, ?)",
                (user_id, username or "", first_name or "", first_name or "")
            )
        else:
            await db.execute(
                "UPDATE users SET username=? WHERE user_id=?",
                (username or "", user_id)
            )
        await db.commit()

async def set_user_field(user_id: int, field: str, value: str):
    allowed = {"nick_bot", "nick_server", "fraction", "uuid"}
    if field not in allowed:
        raise ValueError("Недопустимое поле")
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id, username, first_name FROM users ORDER BY user_id") as cur:
            return await cur.fetchall()

async def find_user_by_nick_server(nick: str):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT user_id, username, nick_server FROM users WHERE LOWER(nick_server)=LOWER(?)",
            (nick,)
        ) as cur:
            return await cur.fetchone()

# ---------- Глобальные ----------
async def set_global(key: str, value: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO globals (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        await db.commit()

async def get_global(key: str, default=""):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT value FROM globals WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

# ---------- Фракции ----------
async def add_faction(name: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO factions (name) VALUES (?)", (name,))
        await db.commit()

async def remove_faction_by_id(fid: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM factions WHERE id=?", (fid,))
        await db.commit()

async def get_factions():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT id, name FROM factions ORDER BY id") as cur:
            return await cur.fetchall()

# ---------- Whitelist ----------
async def add_whitelist(nick: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO whitelist (nick) VALUES (?)", (nick,))
        await db.commit()

async def remove_whitelist_by_id(wid: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM whitelist WHERE id=?", (wid,))
        await db.commit()

async def get_whitelist():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT id, nick FROM whitelist ORDER BY id") as cur:
            return await cur.fetchall()

# ---------- Ссылки ----------
async def add_link(title: str, url: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO links (title, url) VALUES (?, ?)", (title, url))
        await db.commit()

async def remove_link(link_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM links WHERE id=?", (link_id,))
        await db.commit()

async def get_links():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT id, title, url FROM links ORDER BY id") as cur:
            return await cur.fetchall()

# ---------- Картинки ----------
async def set_image(key: str, file_id: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO images (key,file_id) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET file_id=excluded.file_id",
            (key, file_id)
        )
        await db.commit()

async def get_image(key: str):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT file_id FROM images WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def delete_image(key: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM images WHERE key=?", (key,))
        await db.commit()

# ---------- Ресурспак ----------
async def set_resourcepack(file_id: str, instruction: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO resourcepack (key, file_id, instruction) VALUES ('main', ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET file_id=excluded.file_id, instruction=excluded.instruction",
            (file_id, instruction)
        )
        await db.commit()

async def get_resourcepack():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT file_id, instruction FROM resourcepack WHERE key='main'") as cur:
            return await cur.fetchone()

async def delete_resourcepack():
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM resourcepack WHERE key='main'")
        await db.commit()
