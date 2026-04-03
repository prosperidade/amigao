from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CommunicationThread(Base):
    __tablename__ = "communication_threads"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    process_id = Column(Integer, ForeignKey("processes.id"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)

    title = Column(String, nullable=False)
    channel = Column(String, nullable=False) # 'whatsapp', 'email', 'internal'
    external_id = Column(String, nullable=True) # Ex: group ID do WhatsApp

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")
    process = relationship("Process")
    client = relationship("Client")
    messages = relationship("Message", back_populates="thread")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("communication_threads.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    status = Column(String, default="sent") # 'sent', 'delivered', 'read', 'failed'
    external_msg_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("CommunicationThread", back_populates="messages")
    sender = relationship("User")
