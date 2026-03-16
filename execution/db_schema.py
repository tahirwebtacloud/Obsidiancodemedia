from sqlalchemy import Column, String, Integer, JSON, ForeignKey, DateTime, create_engine
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'user_profiles'
    
    user_id = Column(String, primary_key=True)
    brand_name = Column(String)
    primary_color = Column(String)
    secondary_color = Column(String, nullable=True)
    font_family = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    tone_of_voice = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class VoiceEngineProfile(Base):
    __tablename__ = 'voice_engine_profiles'
    
    user_id = Column(String, ForeignKey('user_profiles.user_id'), primary_key=True)
    professional_context = Column(JSON)  # Stores role, career story, etc.
    target_icp = Column(String)
    products_services = Column(JSON, nullable=True)
    messaging_pillars = Column(JSON, nullable=True)
    competitor_positioning = Column(String, nullable=True)

class CRMContact(Base):
    __tablename__ = 'crm_contacts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('user_profiles.user_id'))
    linkedin_url = Column(String)
    full_name = Column(String)
    company = Column(String, nullable=True)
    title = Column(String, nullable=True)
    behavioral_tags = Column(JSON)  # List of strings: ["Warm", "Hot Lead"]
    ai_intent = Column(String, nullable=True)
    ai_summary = Column(String, nullable=True)
    last_interaction_date = Column(DateTime, nullable=True)

def init_db(engine):
    Base.metadata.create_all(engine)
