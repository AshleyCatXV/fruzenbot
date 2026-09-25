import aiosqlite

DB = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                tag TEXT DEFAULT '',
                custom_var TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS globals (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS images (
                key TEXT PRIMARY KEY,
                file_id TEXT
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT user_id, username, tag, custom_var FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            return await cur.fetchone()

async def add_user(user_id: int, username: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()

async def set_user_field(user_id: int, field: str, value: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            return [row[0] for row in await cur.fetchall()]

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