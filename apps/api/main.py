import os
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from apps.api.db import ping_db
from apps.api.models import init_db, SessionLocal, User, Tenant, UserTenant, Asset, Finding
from apps.api.schemas import (
    UserCreate, UserOut, TokenOut,
    TenantCreate, TenantOut,
    AssetCreate, AssetOut,
    FindingOut, FindingUpdate,
)
from apps.api.auth import hash_password, verify_password, create_access_token

app = FastAPI()

# CORS (frontend on :3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    init_db()

# Health
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "CloudSentinel API is running 🚀"}

@app.get("/db/health")
def db_health():
    ok = ping_db()
    return {"database": "ok" if ok else "error"}

# Auth
@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(new_user); db.commit(); db.refresh(new_user)
    return new_user

@app.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.email)
    return {"access_token": token, "token_type": "bearer"}

# Bearer protection
auth_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET", "dev"), algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"email": email}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.get("/me")
def read_me(current_user: dict = Depends(get_current_user)):
    return {"message": "Hello!", "user": current_user}

# helpers
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def ensure_user_in_tenant(db: Session, user_id: int, tenant_id: int):
    link = db.query(UserTenant).filter(
        UserTenant.user_id == user_id, UserTenant.tenant_id == tenant_id
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="User not linked to this tenant")

# Tenants
@app.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(payload: TenantCreate,
                  current_user: dict = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(Tenant).filter(Tenant.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name already exists")
    t = Tenant(name=payload.name)
    db.add(t); db.commit(); db.refresh(t)
    db.add(UserTenant(user_id=user.id, tenant_id=t.id, role="owner")); db.commit()
    return t

@app.get("/tenants", response_model=List[TenantOut])
def list_my_tenants(current_user: dict = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    q = (db.query(Tenant)
           .join(UserTenant, UserTenant.tenant_id == Tenant.id)
           .filter(UserTenant.user_id == user.id))
    return q.all()

# Assets
@app.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(payload: AssetCreate,
                 current_user: dict = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_user_in_tenant(db, user.id, payload.tenant_id)

    a = Asset(
        tenant_id=payload.tenant_id,
        type=payload.type,
        name=payload.name,
        region=payload.region,
        config_json=None if payload.config_json is None else __import__("json").dumps(payload.config_json),
    )
    db.add(a); db.commit(); db.refresh(a)
    return a

@app.get("/assets", response_model=List[AssetOut])
def list_assets(tenant_id: int = Query(..., description="Filter by tenant_id"),
                current_user: dict = Depends(get_current_user),
                db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_user_in_tenant(db, user.id, tenant_id)
    q = db.query(Asset).filter(Asset.tenant_id == tenant_id)
    return q.all()

@app.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: int = Path(..., gt=0),
                 current_user: dict = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    a = db.query(Asset).filter(Asset.id == asset_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    ensure_user_in_tenant(db, user.id, a.tenant_id)
    db.delete(a); db.commit()
    return

# Findings
@app.get("/findings", response_model=List[FindingOut])
def list_findings(tenant_id: int = Query(...), status_f: Optional[str] = Query(None),
                  current_user: dict = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_user_in_tenant(db, user.id, tenant_id)
    q = db.query(Finding).filter(Finding.tenant_id == tenant_id)
    if status_f:
        q = q.filter(Finding.status == status_f)
    return q.order_by(Finding.created_at.desc()).all()

@app.post("/findings/run", response_model=List[FindingOut])
def run_checks(tenant_id: int = Query(...),
               current_user: dict = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Simple demo checks:
       - S3 bucket name not ending with '-prod' => LOW
       - Asset with missing region => MEDIUM
    """
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_user_in_tenant(db, user.id, tenant_id)

    # Clear old open findings for a clean run
    db.query(Finding).filter(Finding.tenant_id == tenant_id, Finding.status == "open").delete()
    db.commit()

    assets = db.query(Asset).filter(Asset.tenant_id == tenant_id).all()
    to_add: List[Finding] = []
    for a in assets:
        if a.type == "aws_s3_bucket" and not a.name.endswith("-prod"):
            to_add.append(Finding(
                tenant_id=tenant_id,
                asset_id=a.id,
                severity="low",
                title="S3 bucket not tagged as production",
                description=f"Bucket '{a.name}' does not end with '-prod'.",
                status="open",
            ))
        if not a.region:
            to_add.append(Finding(
                tenant_id=tenant_id,
                asset_id=a.id,
                severity="medium",
                title="Asset has no region set",
                description=f"Asset '{a.name}' has no region specified.",
                status="open",
            ))
    for f in to_add:
        db.add(f)
    db.commit()

    return db.query(Finding).filter(Finding.tenant_id == tenant_id, Finding.status == "open").all()

@app.patch("/findings/{finding_id}", response_model=FindingOut)
def update_finding(finding_id: int, payload: FindingUpdate,
                   current_user: dict = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    user = get_user_by_email(db, current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    f = db.query(Finding).filter(Finding.id == finding_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    ensure_user_in_tenant(db, user.id, f.tenant_id)
    f.status = payload.status
    db.commit(); db.refresh(f)
    return f
 