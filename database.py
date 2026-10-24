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
                uuid TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                intro_done INTEGER DEFAULT 0
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS globals (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS factions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS whitelist (id INTEGER PRIMARY KEY AUTOINCREMENT, nick TEXT UNIQUE)")
        await db.execute("CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, url TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS images (key TEXT PRIMARY KEY, file_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS resourcepack (key TEXT PRIMARY KEY, file_id TEXT, instruction TEXT)")
        await db.commit()

        # Миграции
        await _ensure_column(db, "users", "first_name", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "nick_bot", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "nick_server", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "fraction", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "uuid", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "tags", "TEXT DEFAULT ''")
        await _ensure_column(db, "users", "intro_done", "INTEGER DEFAULT 0")
        await _ensure_column(db, "factions", "leader_id", "INTEGER DEFAULT 0")

async def _ensure_column(db, table: str, column: str, coltype: str):
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        cols = [row[1] for row in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        await db.commit()

# ---------- Пользователи ----------
async def get_user(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT user_id, username, first_name, nick_bot, nick_server, fraction, uuid, tags, intro_done "
            "FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            return await cur.fetchone()

async def get_user_by_username(username: str):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (username,)) as cur:
            return await cur.fetchone()

async def add_user(user_id: int, username: str, first_name: str = ""):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)) as cur:
            exists = await cur.fetchone()
        if not exists:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, nick_bot) VALUES (?, ?, ?, ?)",
                (user_id, username or "", first_name or "", first_name or "")
            )
        else:
            await db.execute("UPDATE users SET username=? WHERE user_id=?", (username or "", user_id))
        await db.commit()

async def set_user_field(user_id: int, field: str, value):
    allowed = {"nick_bot", "nick_server", "fraction", "uuid", "tags", "intro_done"}
    if field not in allowed: return
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id, username, first_name FROM users ORDER BY user_id") as cur:
            return await cur.fetchall()

# ---------- Теги ----------
def parse_tags(tags_str: str) -> list:
    return [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

async def get_user_tags(user_id: int) -> list:
    u = await get_user(user_id)
    return parse_tags(u[7]) if u else []

async def has_tag(user_id: int, tag: str) -> bool:
    return tag in await get_user_tags(user_id)

async def toggle_user_tag(user_id: int, tag: str):
    u = await get_user(user_id)
    if not u: return False
    tags = parse_tags(u[7])
    if tag in tags:
        tags.remove(tag)
        added = False
    else:
        tags.append(tag)
        added = True
    await set_user_field(user_id, "tags", ",".join(tags))
    return added

# ---------- Глобальные ----------
async def set_global(key: str, value: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO globals (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        await db.commit()

async def get_global(key: str, default=""):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT value FROM globals WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

# ---------- Фракции ----------
async def add_faction(name: str, leader_id: int = 0):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO factions (name, leader_id) VALUES (?, ?)", (name, leader_id))
        await db.commit()

async def set_faction_leader(faction_name: str, leader_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE factions SET leader_id=? WHERE name=?", (leader_id, faction_name))
        await db.commit()

async def remove_faction_by_id(fid: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM factions WHERE id=?", (fid,))
        await db.commit()

async def get_factions():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT id, name, leader_id FROM factions ORDER BY id") as cur:
            return await cur.fetchall()

async def get_faction_by_name(name: str):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT id, name, leader_id FROM factions WHERE LOWER(name)=LOWER(?)", (name,)) as cur:
            return await cur.fetchone()

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

# ---------- Картинки и Ресурспак ----------
async def set_image(key: str, file_id: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO images (key,file_id) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET file_id=excluded.file_id", (key, file_id))
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

async def set_resourcepack(file_id: str, instruction: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO resourcepack (key, file_id, instruction) VALUES ('main', ?, ?) ON CONFLICT(key) DO UPDATE SET file_id=excluded.file_id, instruction=excluded.instruction", (file_id, instruction))
        await db.commit()

async def get_resourcepack():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT file_id, instruction FROM resourcepack WHERE key='main'") as cur:
            return await cur.fetchone()

async def delete_resourcepack():
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM resourcepack WHERE key='main'")
        await db.commit()
# ---------- Whitelist JSON ----------
async def set_whitelist_json(json_text: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO globals (key,value) VALUES ('whitelist_json', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json_text,))
        await db.commit()

async def get_whitelist_json():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT value FROM globals WHERE key='whitelist_json'") as cur:
            row = await cur.fetchone()
            return row[0] if row else None
