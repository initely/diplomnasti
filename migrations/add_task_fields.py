from tortoise import BaseDBAsyncClient

async def upgrade(db: BaseDBAsyncClient):
    await db.execute_script('''
        ALTER TABLE tasks ADD COLUMN subject_code VARCHAR(255) NOT NULL DEFAULT '';
        ALTER TABLE tasks ADD COLUMN local_id INT NOT NULL DEFAULT 1;
    ''')

async def downgrade(db: BaseDBAsyncClient):
    await db.execute_script('''
        -- SQLite не поддерживает DROP COLUMN напрямую, поэтому тут пусто или нужно пересоздавать таблицу
    ''') 