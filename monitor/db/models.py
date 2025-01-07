from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    address = Column(String(42), unique=True, nullable=False)
    health_factor = Column(Float)
    total_collateral_eth = Column(Float)
    total_debt_eth = Column(Float)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    positions = relationship("Position", back_populates="user")
    liquidation_opportunities = relationship("LiquidationOpportunity", back_populates="user")

class Position(Base):
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    token_address = Column(String(42))
    token_symbol = Column(String(10))
    collateral_amount = Column(Float)
    debt_amount = Column(Float)
    collateral_usd = Column(Float)
    debt_usd = Column(Float)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="positions")

class LiquidationOpportunity(Base):
    __tablename__ = 'liquidation_opportunities'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    collateral_token = Column(String(42))
    debt_token = Column(String(42))
    collateral_amount = Column(Float)
    debt_amount = Column(Float)
    health_factor = Column(Float)
    estimated_profit_eth = Column(Float)
    is_profitable = Column(Boolean, default=False)
    executed = Column(Boolean, default=False)
    execution_tx = Column(String(66))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="liquidation_opportunities")

class ScanStatus(Base):
    __tablename__ = 'scan_status'
    
    id = Column(Integer, primary_key=True)
    last_scanned_block = Column(Integer, nullable=False)

def init_db(db_url: str):
    """初始化数据库"""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine