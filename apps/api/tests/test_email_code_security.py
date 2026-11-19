from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.database import Base
from app.models import User
from app.security_services import consume_one_time_code, create_one_time_code


def test_email_code_is_six_digits_and_can_only_be_used_once():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with test_session() as db:
        user = User(email="otp-test@example.com", password_hash="test-hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        code = create_one_time_code(db, user, "register_email_code", 10)

        assert len(code) == 6
        assert code.isdigit()
        assert consume_one_time_code(db, user, "000000" if code != "000000" else "000001", "register_email_code") is False
        assert consume_one_time_code(db, user, code, "register_email_code") is True
        assert consume_one_time_code(db, user, code, "register_email_code") is False

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_resending_email_code_invalidates_previous_code():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with test_session() as db:
        user = User(email="otp-resend@example.com", password_hash="test-hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        with patch("app.security_services.secrets.randbelow", side_effect=[123456, 654321]):
            old_code = create_one_time_code(db, user, "register_email_code", 10)
            new_code = create_one_time_code(db, user, "register_email_code", 10)

        assert consume_one_time_code(db, user, old_code, "register_email_code") is False
        assert consume_one_time_code(db, user, new_code, "register_email_code") is True

    Base.metadata.drop_all(engine)
    engine.dispose()
