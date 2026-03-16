# Phase 1: Database Foundation & Schema Architecture Implementation Plan
**Goal:** Implement the multi-tenant database schema using Pydantic/SQLAlchemy to support User Profiles, Voice Engine, and CRM Contacts.
**Architecture:** Python/SQLAlchemy with SQLite (for dev) or Postgres (for prod). Using Pydantic for data validation.
**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite/Postgres.

---

### Task 1: Define Core Models
**Files:**
- Create: `execution/db_schema.py`
- Test: `tests/test_db_schema.py`

**Step 1: Write the failing test**
```python
# tests/test_db_schema.py
import pytest
from execution.db_schema import UserProfile, VoiceEngineProfile, CRMContact, init_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_schema_creation():
    engine = create_engine('sqlite:///:memory:')
    init_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Test User Profile
    user = UserProfile(
        user_id="test_user_123",
        brand_name="Test Brand",
        primary_color="#FF0000",
        tone_of_voice="Professional"
    )
    session.add(user)
    session.commit()
    
    saved_user = session.query(UserProfile).filter_by(user_id="test_user_123").first()
    assert saved_user.brand_name == "Test Brand"
    
    # Test Voice Profile (JSONB)
    voice = VoiceEngineProfile(
        user_id="test_user_123",
        professional_context={"role": "Founder"},
        target_icp="CTOs"
    )
    session.add(voice)
    session.commit()
    
    saved_voice = session.query(VoiceEngineProfile).filter_by(user_id="test_user_123").first()
    assert saved_voice.professional_context["role"] == "Founder"
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_db_schema.py`
Expected: `ModuleNotFoundError: No module named 'execution.db_schema'`

**Step 3: Write minimal implementation**
```python
# execution/db_schema.py
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
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_db_schema.py`
Expected: PASS

**Step 5: Commit**
`git add execution/db_schema.py tests/test_db_schema.py`
`git commit -m "feat: Implement core database schema"`
