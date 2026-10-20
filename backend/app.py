import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Text, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
URL=os.getenv("DATABASE_URL","sqlite:///./aquaforma.db")
if URL.startswith("postgres://"): URL=URL.replace("postgres://","postgresql://",1)
engine=create_engine(URL,pool_pre_ping=True,connect_args={"check_same_thread":False} if URL.startswith("sqlite") else {})
Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)
app=FastAPI(title="AquaForma API",version="1.0.0")
origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=["*"] if "*" in origins else origins,allow_credentials=False,allow_methods=["GET","POST","OPTIONS"],allow_headers=["Content-Type"])
class Base(DeclarativeBase): pass
class Enquiry(Base):
 __tablename__="enquiries"
 id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
 name:Mapped[str]=mapped_column(String(120),nullable=False)
 email:Mapped[str]=mapped_column(String(254),nullable=False)
 country:Mapped[Optional[str]]=mapped_column(String(160),nullable=True)
 project_type:Mapped[str]=mapped_column(String(80),nullable=False)
 message:Mapped[str]=mapped_column(Text,nullable=False)
 language:Mapped[str]=mapped_column(String(5),nullable=False,default="en")
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
Base.metadata.create_all(engine)
class Contact(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 email:EmailStr
 country:str=Field(default="",max_length=160)
 project_type:str=Field(min_length=2,max_length=80)
 message:str=Field(min_length=10,max_length=5000)
 language:str=Field(default="en",pattern="^(ru|pl|en|de)$")
@app.get("/")
def root(): return {"service":"AquaForma API","status":"ok","docs":"/docs"}
@app.get("/health")
def health():
 try:
  with engine.connect() as c: c.exec_driver_sql("SELECT 1")
  return {"status":"healthy","database":"connected"}
 except Exception: raise HTTPException(503,"Database unavailable")
@app.post("/api/contact",status_code=201)
def contact(p:Contact):
 db=Session()
 try:
  row=Enquiry(name=p.name.strip(),email=str(p.email),country=p.country.strip(),project_type=p.project_type.strip(),message=p.message.strip(),language=p.language)
  db.add(row);db.commit();db.refresh(row)
  return {"ok":True,"id":row.id,"message":"Enquiry received"}
 except Exception:
  db.rollback();raise HTTPException(500,"Could not save enquiry")
 finally: db.close()
