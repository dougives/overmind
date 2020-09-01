from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import dotenv

dotenv.load_dotenv()

_engine = create_engine(os.environ['DATABASE_CONNECTION_STRING'])
Session = sessionmaker(bind=_engine)
session = _Session()


