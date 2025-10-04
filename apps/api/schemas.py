from typing import Optional, Any, Dict
from pydantic import BaseModel, EmailStr

# ---------- Users ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True  # Pydantic v2: allow ORM objects


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Tenants ----------
class TenantCreate(BaseModel):
    name: str

class TenantOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# ---------- Assets ----------
class AssetCreate(BaseModel):
    tenant_id: int
    type: str
    name: str
    region: Optional[str] = None
    # keep for future if you want to send extra config
    config_json: Optional[Dict[str, Any]] = None

class AssetOut(BaseModel):
    id: int
    tenant_id: int
    type: str
    name: str
    region: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Findings ----------
class FindingOut(BaseModel):
    id: int
    tenant_id: int
    asset_id: int
    severity: str           # "low" | "medium" | "high"
    status: str             # "open" | "resolved" | "ignored"
    title: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

class FindingUpdate(BaseModel):
    status: str             # "open" | "resolved" | "ignored"
