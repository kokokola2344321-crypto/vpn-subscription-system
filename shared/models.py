"""
ORM модели для базы данных
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    sub_type = Column(String, default="none")  # none, normal, antiblock, both
    sub_expires_at = Column(DateTime, nullable=True)
    referrer_id = Column(String, nullable=True, index=True)
    is_test_used = Column(Boolean, default=False)
    subscription_token = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = relationship("Payment", back_populates="user")

    def __repr__(self):
        return f"<User {self.telegram_id}>"


class Admin(Base):
    """Модель администратора"""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="admin")  # owner, admin
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Admin {self.telegram_id} ({self.role})>"


class GlobalConfig(Base):
    """Глобальные конфигурации"""
    __tablename__ = "global_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Config {self.key}>"


class PromoCode(Base):
    """Модель промокода"""
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    reward = Column(Float, nullable=False)
    uses_left = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PromoCode {self.code}>"


class Payment(Base):
    """Модель платежа"""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="payments")

    def __repr__(self):
        return f"<Payment {self.id} - {self.status}>"


class Referral(Base):
    """Модель реферала"""
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(String, index=True, nullable=False)
    referred_id = Column(String, index=True, nullable=False, unique=True)
    reward_given = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Referral {self.referrer_id} -> {self.referred_id}>"
