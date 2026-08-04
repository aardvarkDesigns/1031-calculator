"""Database models for 1031 Exchange Calculator."""

from sqlalchemy import create_engine, Column, String, Integer, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()
DATABASE_URL = "sqlite:///properties.db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


class Property(Base):
    """Property data model."""
    __tablename__ = 'properties'

    apn = Column(String(20), primary_key=True, index=True)
    property_address = Column(String(255))
    city = Column(String(100))
    zip_code = Column(String(10))

    # Calculator inputs
    sale_price = Column(Integer)  # Purchase Price
    current_home_value = Column(Integer)  # Market Value (AVM)

    # Mortgage info for calculation
    first_mortgage_amt = Column(Integer)  # Original mortgage amount
    mortgage_rate = Column(Float)  # Interest rate (as percentage, e.g., 6.35)
    mortgage_date = Column(Date)  # When mortgage was taken

    # Additional property info
    year_built = Column(Integer)
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    building_sqft = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AccessLog(Base):
    """Access log for tracking calculator usage."""
    __tablename__ = 'access_logs'

    id = Column(Integer, primary_key=True)
    apn = Column(String(20), ForeignKey('properties.apn'), index=True)
    accessed_at = Column(DateTime, default=datetime.utcnow)
    session_duration_seconds = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<AccessLog APN={self.apn} at {self.accessed_at}>"


def init_db():
    """Initialize database."""
    Base.metadata.create_all(engine)


def get_session():
    """Get database session."""
    return Session()
