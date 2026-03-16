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
