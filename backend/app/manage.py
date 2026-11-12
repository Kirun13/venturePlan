"""Local administrative operations. No HTTP access is provided."""
import argparse
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.engine import make_url
from app.config import get_settings
from app.db.models import PlanJob, Project, User
from app.db.session import Session, engine


async def adopt_legacy(email):
    async with Session.begin() as session:
        user = await session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise ValueError("Create the user account first")
        rows = (await session.scalars(select(PlanJob).where(PlanJob.owner_id.is_(None)).with_for_update())).all()
        for job in rows:
            project = Project(owner_id=user.id, name=job.input_data.get("name", "Imported plan"))
            session.add(project)
            await session.flush()
            job.owner_id, job.project_id, job.version = user.id, project.id, 1
    print(f"Assigned {len(rows)} legacy plans")
    await engine.dispose()


def backup(output, executable):
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Backup requires PostgreSQL")
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("Choose a new backup filename")
    temporary = destination.with_suffix(destination.suffix + ".partial")
    env = {**os.environ, "PGHOST":url.host or "localhost", "PGPORT":str(url.port or 5432),
           "PGUSER":url.username or "", "PGPASSWORD":url.password or "", "PGDATABASE":url.database or ""}
    # Pass credentials through environment, never arguments or logs.
    subprocess.run([executable, "--format=custom", "--file", str(temporary)], env=env, check=True)
    temporary.replace(destination)
    print(f"Backup saved to {destination}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    adopt = sub.add_parser("adopt-legacy")
    adopt.add_argument("--email", required=True)
    dump = sub.add_parser("backup")
    dump.add_argument("--output", required=True)
    dump.add_argument("--pg-dump", default=shutil.which("pg_dump") or "pg_dump")
    args = parser.parse_args()
    if args.command == "adopt-legacy":
        asyncio.run(adopt_legacy(args.email))
    else:
        backup(args.output, args.pg_dump)


if __name__ == "__main__":
    main()
