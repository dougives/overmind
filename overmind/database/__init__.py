from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
import dotenv

dotenv.load_dotenv()

_engine = create_engine(os.environ['DATABASE_CONNECTION_STRING'])
session_factory = sessionmaker(bind=_engine)
Session = scoped_session(session_factory)
pass

