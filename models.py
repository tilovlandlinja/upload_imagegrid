from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()  # Bruk Base som utgangspunkt for alle modeller

class UploadTracker(Base):
    __tablename__ = 'upload_tracker'
    
    id = Column(Integer, primary_key=True)
    folder = Column(String(150), nullable=False)
    upload_type = Column(String(50), nullable=False)
    total_images = Column(Integer, default=0)
    uploaded_images = Column(Integer, default=0)
    failed_images = Column(Integer, default=0)
    upload_done = Column(String(100), default=0)
    last_upload_time = Column(String(100), default='Never')

    def __repr__(self):
        return f'<Folder {self.folder}>'
