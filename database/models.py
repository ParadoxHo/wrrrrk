from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    allow_random_chat = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    interviews = relationship("Interview", back_populates="user", lazy="dynamic")
    stats = relationship("UserStats", back_populates="user", uselist=False)

class Interview(Base):
    __tablename__ = 'interviews'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    profession = Column(String)
    level = Column(String)
    persona = Column(String)
    language = Column(String)
    total_questions = Column(Integer)
    resume_text = Column(Text, nullable=True)
    vacancy_text = Column(Text, nullable=True)
    history = Column(JSON)
    report = Column(Text)
    metrics = Column(JSON)
    hints_used = Column(Integer, default=0)
    early_stop = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="interviews")

class UserStats(Base):
    __tablename__ = 'user_stats'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    total_interviews = Column(Integer, default=0)
    average_score = Column(Float, default=0.0)
    strengths = Column(JSON)
    weaknesses = Column(JSON)
    recommendations = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="stats")

class ChatQueue(Base):
    __tablename__ = 'chat_queue'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

class ActiveChat(Base):
    __tablename__ = 'active_chats'
    id = Column(Integer, primary_key=True)
    user1_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user2_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Integer, default=1)

class Relationship(Base):
    __tablename__ = 'relationships'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    scenario_key = Column(String, nullable=False)   # 'date', 'internet_meeting'
    interest = Column(Float, default=30.0)
    trust = Column(Float, default=20.0)
    romance = Column(Float, default=10.0)
    interaction_count = Column(Integer, default=0)
    last_history_summary = Column(Text)
    last_interaction = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
