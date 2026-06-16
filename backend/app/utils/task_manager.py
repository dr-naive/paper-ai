"""任务状态管理 - 用于异步上传进度跟踪"""

import asyncio
import json
import os
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime
from pathlib import Path

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskProgress:
    """任务进度信息"""
    
    def __init__(self, task_id: str, paper_id: str, user_id: str):
        self.task_id = task_id
        self.paper_id = paper_id
        self.user_id = user_id
        self.status: TaskStatus = TaskStatus.PENDING
        self.progress: int = 0
        self.message: str = ""
        self.details: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

# 获取任务存储目录
def get_task_storage_dir():
    storage_dir = Path("./data/tasks")
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir

def get_task_file_path(task_id: str):
    return get_task_storage_dir() / f"{task_id}.json"

def create_task(paper_id: str, user_id: str) -> TaskProgress:
    """创建任务"""
    task_id = f"task_{paper_id}"
    task = TaskProgress(task_id, paper_id, user_id)
    
    # 存储到文件
    task_data = {
        "task_id": task.task_id,
        "paper_id": task.paper_id,
        "user_id": task.user_id,
        "status": task.status.value,
        "progress": task.progress,
        "message": task.message,
        "details": task.details,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat()
    }
    
    file_path = get_task_file_path(task_id)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)
    
    return task

def get_task(task_id: str) -> Optional[TaskProgress]:
    """获取任务状态"""
    file_path = get_task_file_path(task_id)
    
    if not file_path.exists():
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            task_dict = json.load(f)
        
        task = TaskProgress(task_dict['task_id'], task_dict['paper_id'], task_dict['user_id'])
        task.status = TaskStatus(task_dict['status'])
        task.progress = int(task_dict['progress'])
        task.message = task_dict['message']
        task.details = task_dict.get('details', {})
        task.created_at = datetime.fromisoformat(task_dict['created_at'])
        task.updated_at = datetime.fromisoformat(task_dict['updated_at'])
        
        return task
    except Exception:
        return None

def update_task(task_id: str, **kwargs):
    """更新任务状态"""
    file_path = get_task_file_path(task_id)
    
    if not file_path.exists():
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            task_dict = json.load(f)
        
        # 更新字段
        for key, value in kwargs.items():
            if key == 'status' and isinstance(value, TaskStatus):
                task_dict[key] = value.value
            else:
                task_dict[key] = value
        
        task_dict['updated_at'] = datetime.now().isoformat()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(task_dict, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def remove_task(task_id: str):
    """移除任务"""
    file_path = get_task_file_path(task_id)
    if file_path.exists():
        file_path.unlink()