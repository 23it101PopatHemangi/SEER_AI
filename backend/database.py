import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# Load environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./seer_ai.db")

# Setup database connection arguments (SQLite requires check_same_thread=False)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    repositories = relationship("Repository", back_populates="project", cascade="all, delete-orphan")

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    github_url = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    default_branch = Column(String, nullable=False, default="main")
    primary_language = Column(String, nullable=True)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    open_issues_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_pushed_at = Column(DateTime, nullable=False)

    project = relationship("Project", back_populates="repositories")

class UserToken(Base):
    __tablename__ = "user_tokens"

    user_email = Column(String, primary_key=True, index=True)
    github_access_token = Column(String, nullable=False)
    github_username = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
