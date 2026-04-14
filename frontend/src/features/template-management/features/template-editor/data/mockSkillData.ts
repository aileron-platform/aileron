import type { FileNode } from '../hooks/useTemplateFileManagement';

export const mockSkillTree: FileNode[] = [
  {
    id: 'folder-1',
    name: 'frontend',
    type: 'directory',
    path: 'frontend',
    children: [
      {
        id: 'file-1',
        name: 'react-component.tsx',
        type: 'file',
        path: 'frontend/react-component.tsx',
        content: `import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';

interface UserCardProps {
  userId: string;
  onUpdate?: (data: any) => void;
}

export const UserCard: React.FC<UserCardProps> = ({ userId, onUpdate }) => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await fetch(\`/api/users/\${userId}\`);
        const data = await response.json();
        setUser(data);
      } catch (error) {
        console.error('Failed to fetch user:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [userId]);

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>User not found</div>;

  return (
    <div className="p-4 border rounded-lg">
      <h2 className="text-xl font-bold">{user.name}</h2>
      <p className="text-gray-600">{user.email}</p>
      <Button onClick={() => onUpdate?.(user)}>
        Update
      </Button>
    </div>
  );
};`,
      },
      {
        id: 'file-2',
        name: 'hooks.ts',
        type: 'file',
        path: 'frontend/hooks.ts',
        content: `import { useState, useEffect, useCallback } from 'react';

/**
 * Custom hook for data fetching with loading and error states
 */
export function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(\`HTTP error! status: \${response.status}\`);
      }
      const result = await response.json();
      setData(result);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}

/**
 * Custom hook for local storage
 */
export function useLocalStorage<T>(key: string, initialValue: T) {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(error);
      return initialValue;
    }
  });

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue] as const;
}`,
      },
      {
        id: 'file-3',
        name: 'best-practices.md',
        type: 'file',
        path: 'frontend/best-practices.md',
        content: `# React 最佳實踐

## 組件設計原則
1. 單一職責原則 - 每個組件只做一件事
2. 組件應該是可重用的
3. 使用 TypeScript 進行類型檢查
4. Props 應該有明確的類型定義

## Hooks 使用規範
- 只在最頂層使用 Hook
- 只在 React 函數中調用 Hook
- 自定義 Hook 以 "use" 開頭
- 使用 useCallback 和 useMemo 優化性能

## 性能優化
- 使用 React.memo 避免不必要的重渲染
- 使用 useMemo 和 useCallback 優化計算和回調
- 使用 lazy 和 Suspense 進行代碼分割
- 避免在 render 中創建新的對象或函數

## 狀態管理
- 優先使用 Context API 進行簡單的狀態共享
- 複雜狀態使用 Redux 或 Zustand
- 服務器狀態使用 React Query 或 SWR`,
      },
    ],
  },
  {
    id: 'folder-2',
    name: 'backend',
    type: 'directory',
    path: 'backend',
    children: [
      {
        id: 'file-4',
        name: 'api_service.py',
        type: 'file',
        path: 'backend/api_service.py',
        content: `"""
FastAPI 服務範例
提供用戶管理的 RESTful API
"""
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import uvicorn

app = FastAPI(title="User Management API", version="1.0.0")

# 資料模型
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool = True

    class Config:
        from_attributes = True

# 模擬資料庫
fake_users_db = {}
user_id_counter = 1

@app.get("/")
async def root():
    """健康檢查端點"""
    return {"status": "healthy", "message": "User Management API is running"}

@app.post("/users/", response_model=User, status_code=201)
async def create_user(user: UserCreate):
    """創建新用戶"""
    global user_id_counter

    # 檢查用戶是否已存在
    for existing_user in fake_users_db.values():
        if existing_user["email"] == user.email:
            raise HTTPException(status_code=400, detail="Email already registered")

    # 創建用戶
    user_dict = user.dict()
    user_dict["id"] = user_id_counter
    user_dict["is_active"] = True
    del user_dict["password"]  # 不返回密碼

    fake_users_db[user_id_counter] = user_dict
    user_id_counter += 1

    return user_dict

@app.get("/users/", response_model=List[User])
async def list_users(skip: int = 0, limit: int = 100):
    """獲取用戶列表"""
    users = list(fake_users_db.values())
    return users[skip : skip + limit]

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    """獲取單個用戶"""
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return fake_users_db[user_id]

@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: UserBase):
    """更新用戶信息"""
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")

    user_dict = user.dict()
    user_dict["id"] = user_id
    user_dict["is_active"] = fake_users_db[user_id]["is_active"]

    fake_users_db[user_id] = user_dict
    return user_dict

@app.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """刪除用戶"""
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")

    del fake_users_db[user_id]
    return None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)`,
      },
      {
        id: 'file-5',
        name: 'database.py',
        type: 'file',
        path: 'backend/database.py',
        content: `"""
資料庫連接和操作工具
使用 SQLAlchemy ORM
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# 資料庫配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

# 創建引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=True  # 開發環境顯示 SQL
)

# 創建 Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 類
Base = declarative_base()

# 用戶模型
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"

# 創建所有表
def init_db():
    """初始化資料庫"""
    Base.metadata.create_all(bind=engine)

# 獲取資料庫 session
def get_db():
    """依賴注入：獲取資料庫 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 資料庫操作類
class UserRepository:
    """用戶資料庫操作"""

    def __init__(self, db):
        self.db = db

    def create(self, user_data: dict):
        """創建用戶"""
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int):
        """根據 ID 獲取用戶"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str):
        """根據 email 獲取用戶"""
        return self.db.query(User).filter(User.email == email).first()

    def list_all(self, skip: int = 0, limit: int = 100):
        """獲取用戶列表"""
        return self.db.query(User).offset(skip).limit(limit).all()

    def update(self, user_id: int, user_data: dict):
        """更新用戶"""
        user = self.get_by_id(user_id)
        if user:
            for key, value in user_data.items():
                setattr(user, key, value)
            self.db.commit()
            self.db.refresh(user)
        return user

    def delete(self, user_id: int):
        """刪除用戶"""
        user = self.get_by_id(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
        return user`,
      },
      {
        id: 'file-6',
        name: 'utils.py',
        type: 'file',
        path: 'backend/utils.py',
        content: `"""
通用工具函數
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt

SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    """密碼加密"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}$\${pwd_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """驗證密碼"""
    try:
        salt, pwd_hash = hashed.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return new_hash.hex() == pwd_hash
    except:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """創建 JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    """解碼 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None`,
      },
    ],
  },
  {
    id: 'folder-3',
    name: 'scripts',
    type: 'directory',
    path: 'scripts',
    children: [
      {
        id: 'file-7',
        name: 'deploy.sh',
        type: 'file',
        path: 'scripts/deploy.sh',
        content: `#!/bin/bash

# 部署腳本
# 用於自動化部署應用到生產環境

set -e  # 遇到錯誤立即退出

# 顏色輸出
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# 配置
APP_NAME="my-app"
DEPLOY_DIR="/var/www/\${APP_NAME}"
BACKUP_DIR="/var/backups/\${APP_NAME}"
GIT_REPO="git@github.com:user/repo.git"
BRANCH="main"

echo -e "\${GREEN}========================================\${NC}"
echo -e "\${GREEN}開始部署 \${APP_NAME}\${NC}"
echo -e "\${GREEN}========================================\${NC}"

# 1. 備份當前版本
echo -e "\${YELLOW}[1/6] 備份當前版本...\${NC}"
if [ -d "\${DEPLOY_DIR}" ]; then
    TIMESTAMP=\\$(date +%Y%m%d_%H%M%S)
    mkdir -p "\${BACKUP_DIR}"
    tar -czf "\${BACKUP_DIR}/backup_\${TIMESTAMP}.tar.gz" -C "\${DEPLOY_DIR}" .
    echo -e "\${GREEN}✓ 備份完成: backup_\${TIMESTAMP}.tar.gz\${NC}"
else
    echo -e "\${YELLOW}⚠ 首次部署，跳過備份\${NC}"
fi

# 2. 拉取最新代碼
echo -e "\${YELLOW}[2/6] 拉取最新代碼...\${NC}"
if [ -d "\${DEPLOY_DIR}/.git" ]; then
    cd "\${DEPLOY_DIR}"
    git fetch origin
    git checkout "\${BRANCH}"
    git pull origin "\${BRANCH}"
else
    mkdir -p "\${DEPLOY_DIR}"
    git clone -b "\${BRANCH}" "\${GIT_REPO}" "\${DEPLOY_DIR}"
    cd "\${DEPLOY_DIR}"
fi
echo -e "\${GREEN}✓ 代碼更新完成\${NC}"

# 3. 安裝依賴
echo -e "\${YELLOW}[3/6] 安裝依賴...\${NC}"
if [ -f "package.json" ]; then
    npm install --production
    echo -e "\${GREEN}✓ Node.js 依賴安裝完成\${NC}"
fi

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "\${GREEN}✓ Python 依賴安裝完成\${NC}"
fi

# 4. 構建應用
echo -e "\${YELLOW}[4/6] 構建應用...\${NC}"
if [ -f "package.json" ]; then
    npm run build
    echo -e "\${GREEN}✓ 前端構建完成\${NC}"
fi

# 5. 運行數據庫遷移
echo -e "\${YELLOW}[5/6] 運行數據庫遷移...\${NC}"
if [ -f "manage.py" ]; then
    python manage.py migrate
    echo -e "\${GREEN}✓ 數據庫遷移完成\${NC}"
fi

# 6. 重啟服務
echo -e "\${YELLOW}[6/6] 重啟服務...\${NC}"
sudo systemctl restart "\${APP_NAME}"
sleep 3

# 檢查服務狀態
if sudo systemctl is-active --quiet "\${APP_NAME}"; then
    echo -e "\${GREEN}✓ 服務重啟成功\${NC}"
else
    echo -e "\${RED}✗ 服務重啟失敗\${NC}"
    exit 1
fi

echo -e "\${GREEN}========================================\${NC}"
echo -e "\${GREEN}部署完成！\${NC}"
echo -e "\${GREEN}========================================\${NC}"`,
      },
      {
        id: 'file-8',
        name: 'backup.sh',
        type: 'file',
        path: 'scripts/backup.sh',
        content: `#!/bin/bash

# 資料庫備份腳本
# 每日自動備份資料庫並清理舊備份

set -e

# 配置
DB_NAME="myapp_db"
DB_USER="postgres"
BACKUP_DIR="/var/backups/database"
RETENTION_DAYS=7

# 創建備份目錄
mkdir -p "\${BACKUP_DIR}"

# 生成備份檔案名
TIMESTAMP=\\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\${BACKUP_DIR}/\${DB_NAME}_\${TIMESTAMP}.sql.gz"

echo "開始備份資料庫: \${DB_NAME}"
echo "備份檔案: \${BACKUP_FILE}"

# 執行備份
pg_dump -U "\${DB_USER}" "\${DB_NAME}" | gzip > "\${BACKUP_FILE}"

# 檢查備份是否成功
if [ -f "\${BACKUP_FILE}" ]; then
    SIZE=\\$(du -h "\${BACKUP_FILE}" | cut -f1)
    echo "✓ 備份成功 (大小: \${SIZE})"
else
    echo "✗ 備份失敗"
    exit 1
fi

# 清理舊備份
echo "清理 \${RETENTION_DAYS} 天前的備份..."
find "\${BACKUP_DIR}" -name "\${DB_NAME}_*.sql.gz" -mtime +\${RETENTION_DAYS} -delete
echo "✓ 清理完成"

echo "備份流程完成"`,
      },
    ],
  },
  {
    id: 'file-9',
    name: 'README.md',
    type: 'file',
    path: 'README.md',
    content: `# 技能知識庫

這個目錄包含了各種開發技能和最佳實踐的範例代碼。

## 目錄結構

### frontend/
前端開發相關的技能和範例
- \`react-component.tsx\` - React 組件範例
- \`hooks.ts\` - 自定義 Hooks 範例
- \`best-practices.md\` - React 最佳實踐指南

### backend/
後端開發相關的技能和範例
- \`api_service.py\` - FastAPI 服務範例
- \`database.py\` - SQLAlchemy 資料庫操作
- \`utils.py\` - 通用工具函數

### scripts/
自動化腳本
- \`deploy.sh\` - 部署腳本
- \`backup.sh\` - 資料庫備份腳本

## 使用方式

這些範例代碼可以作為：
1. 學習參考
2. 項目模板
3. 代碼片段庫
4. 最佳實踐指南

## 技術棧

- **前端**: React, TypeScript, Hooks
- **後端**: Python, FastAPI, SQLAlchemy
- **資料庫**: PostgreSQL
- **部署**: Bash Scripts, systemd

## 貢獻

歡迎添加更多技能範例和最佳實踐！`,
  },
];

