"""Database models for 1031 Exchange Calculator."""

from sqlalchemy import create_engine, Column, String, Integer, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()
DATABASE_URL = "sqlite:///properties.db"
engine = create_engine(DATABASE_URL, echo=False)
# expire_on_commit=False: routes commit() (e.g. to log an access) and then
# keep reading the same object after the session closes. Without this,
# SQLAlchemy expires the object's attributes on commit and every later
# attribute access raises DetachedInstanceError once the session is closed.
Session = sessionmaker(bind=engine, expire_on_commit=False)


class Property(Base):
    """Property data model."""
    __tablename__ = 'properties'

    property_id = Column(String(20), primary_key=True, index=True)  # County APN / parcel number
    property_address = Column(String(255))
    city = Column(String(100))
    zip_code = Column(String(10))

    # Calculator inputs
    sale_price = Column(Integer)  # Purchase Price
    sale_date = Column(Date)  # Reference only -- not used in calculator math
    current_home_value = Column(Integer)  # Market Value (AVM) -- Current Value

    # Mortgage info for calculation. Left NULL for postcard-driven properties so
    # calculate_mortgage_payoff() in app.py returns the required constant of $0
    # for "Mortgage Pay Off". Populate these later if per-property mortgage
    # payoff calculation is ever needed.
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
    property_id = Column(String(20), ForeignKey('properties.property_id'), index=True)
    accessed_at = Column(DateTime, default=datetime.utcnow)
    session_duration_seconds = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<AccessLog PropertyID={self.property_id} at {self.accessed_at}>"


def init_db():
    """Initialize database."""
    Base.metadata.create_all(engine)


def get_session():
    """Get database session."""
    return Session()
