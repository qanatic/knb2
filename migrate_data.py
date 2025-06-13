from app import db, Author, UploadedFile  # Імпортуємо з app.py
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import os

# 🔁 URI до твоєї Supabase бази (Transaction Pooler, IPv4)
supabase_uri = 'postgresql://postgres.hpmfkifmugvnbmlggsex:Qwe123rty%40@aws-0-eu-north-1.pooler.supabase.com:6543/postgres'

# 🔁 URI до SQLite
sqlite_uri = 'sqlite:///database.db'

# Підключення до обох баз
source_engine = create_engine(sqlite_uri)
target_engine = create_engine(supabase_uri)

# Зчитуємо дані з SQLite
with Session(source_engine) as source_session, Session(target_engine) as target_session:
    authors = source_session.query(Author).all()
    for author in authors:
        target_session.merge(author)

    files = source_session.query(UploadedFile).all()
    for file in files:
        # Зв’язки many-to-many теж можна перенести
        new_file = UploadedFile(
            id=file.id,
            filename=file.filename,
            filepath=file.filepath,
            upload_date=file.upload_date,
            publisher=file.publisher,
            authors=file.authors  # SQLAlchemy сам розпізнає
        )
        target_session.merge(new_file)

    target_session.commit()
