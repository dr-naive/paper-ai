"""用户认证 API 模块"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Literal
import uuid
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@paperai.local"


class Token(BaseModel):
    access_token: str
    token_type: str
    
    model_config = {"from_attributes": True}


class TokenData(BaseModel):
    user_id: str | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: Literal["admin", "user"]
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class UserPermissionUpdate(BaseModel):
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).filter(User.id == token_data.user_id))
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


async def ensure_default_admin() -> None:
    """Ensure the built-in administrator exists with credentials from environment configuration."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).filter(User.username == DEFAULT_ADMIN_USERNAME)
        )
        admin = result.scalars().first()
        password_hash = get_password_hash(settings.DEFAULT_ADMIN_PASSWORD)
        if admin is None:
            email_owner = await db.execute(
                select(User).filter(User.email == DEFAULT_ADMIN_EMAIL)
            )
            admin_email = (
                f"admin+{uuid.uuid4()}@paperai.local"
                if email_owner.scalars().first()
                else DEFAULT_ADMIN_EMAIL
            )
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                email=admin_email,
                password_hash=password_hash,
                role="admin",
                is_active=True,
            )
            db.add(admin)
        else:
            # This account is deliberately immutable from the permission API.
            # Restore its required state on every application start.
            admin.password_hash = password_hash
            admin.role = "admin"
            admin.is_active = True
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Another application worker may have created it concurrently.
            result = await db.execute(
                select(User).filter(User.username == DEFAULT_ADMIN_USERNAME)
            )
            admin = result.scalars().first()
            if admin is None:
                raise
            admin.password_hash = password_hash
            admin.role = "admin"
            admin.is_active = True
            await db.commit()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=LoginResponse)
async def login_for_access_token(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter((User.email == login_data.username) | (User.username == login_data.username)))
    user = result.scalars().first()
    
    if (
        not user
        or not user.is_active
        or not verify_password(login_data.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)
    return {"access_token": access_token, "user": UserResponse.from_orm(user)}


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    existing_user = result.scalars().first()
    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(status_code=400, detail="该邮箱已注册")
        raise HTTPException(status_code=400, detail="该用户名已被使用")
    
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role="user",
    )
    
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="用户名或邮箱已被使用")
    await db.refresh(new_user)
    return UserResponse.from_orm(new_user)


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm(current_user)


@router.get("/admin/users", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserResponse.from_orm(user) for user in result.scalars().all()]


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
async def update_user_permissions(
    user_id: str,
    update: UserPermissionUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == DEFAULT_ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail="系统默认管理员不能被修改")
    if update.role is not None:
        user.role = update.role
    if update.is_active is not None:
        user.is_active = update.is_active
    await db.commit()
    await db.refresh(user)
    return UserResponse.from_orm(user)
