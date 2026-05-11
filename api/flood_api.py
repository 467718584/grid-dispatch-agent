"""
防洪方案本地存储API

保存防洪方案到本地文件，提供下载接口
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import json
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/flood", tags=["flood"])

# 本地存储目录
STORAGE_DIR = "/tmp/flood_schemes"
os.makedirs(STORAGE_DIR, exist_ok=True)


class FloodSchemeRequest(BaseModel):
    """防洪方案保存请求"""
    task: str
    scheme_name: str
    scheme_data: dict
    description: Optional[str] = ""


@router.post("/save")
async def save_flood_scheme(request: FloodSchemeRequest):
    """
    保存防洪方案到本地
    
    请求体:
    {
        "task": "今天的防洪调度预报",
        "scheme_name": "防洪方案_20250509",
        "scheme_data": {...},
        "description": "可选描述"
    }
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"flood_scheme_{timestamp}.json"
    filepath = os.path.join(STORAGE_DIR, filename)
    
    save_data = {
        "task": request.task,
        "scheme_name": request.scheme_name,
        "description": request.description,
        "created_at": timestamp,
        "data": request.scheme_data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    return {
        "success": True,
        "filename": filename,
        "filepath": filepath,
        "download_url": f"/flood/download/{filename}"
    }


@router.get("/download/{filename}")
async def download_flood_scheme(filename: str):
    """下载防洪方案JSON文件"""
    # 安全检查：只允许下载tmp目录下的文件
    if '..' in filename or '/' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    filepath = os.path.join(STORAGE_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        media_type="application/json",
        filename=filename
    )


@router.get("/list")
async def list_flood_schemes():
    """列出所有保存的防洪方案"""
    files = []
    for f in os.listdir(STORAGE_DIR):
        if f.endswith('.json'):
            filepath = os.path.join(STORAGE_DIR, f)
            stat = os.stat(filepath)
            files.append({
                "filename": f,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    
    return {
        "total": len(files),
        "files": sorted(files, key=lambda x: x["created"], reverse=True)
    }


@router.get("/get/{filename}")
async def get_flood_scheme(filename: str):
    """获取防洪方案内容"""
    if '..' in filename or '/' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    filepath = os.path.join(STORAGE_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data
