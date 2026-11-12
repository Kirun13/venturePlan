import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.db.models import Base
config = context.config

def run_offline():
    context.configure(url=get_settings().database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

async def run_online():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        await conn.run_sync(run_sync_migrations)
    await engine.dispose()

def run_sync_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
