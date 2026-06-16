#!/usr/bin/env python3
"""
Skill 打包工具 - 将 skills 文件夹打包成 .skill 文件

使用方法:
    python build_skill.py [--name <skill_name>] [--output <output_path>]

示例:
    python build_skill.py --name my_skill --output ./
"""
import os
import sys
import json
import zipfile
import argparse
from pathlib import Path
from datetime import datetime


def create_skill_package(skill_dir: str, output_dir: str = "./") -> str:
    """
    创建 .skill 包
    
    Args:
        skill_dir: Skill 目录路径
        output_dir: 输出目录
    
    Returns:
        生成的 .skill 文件路径
    """
    skill_path = Path(skill_dir)
    
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill 目录不存在: {skill_dir}")
    
    # 读取 manifest.json
    manifest_path = skill_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("manifest.json 不存在")
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    skill_name = manifest.get("name", skill_path.name)
    version = manifest.get("version", "1.0.0")
    
    # 生成输出文件名
    output_file = Path(output_dir) / f"{skill_name}.skill"
    
    # 创建 ZIP 包
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加 manifest
        zf.write(manifest_path, "manifest.json")
        
        # 添加 skill.md
        skill_md = skill_path / "skill.md"
        if skill_md.exists():
            zf.write(skill_md, "skill.md")
        
        # 添加所有 Python 文件
        for py_file in skill_path.rglob("*.py"):
            arcname = str(py_file.relative_to(skill_path))
            zf.write(py_file, arcname)
        
        # 添加其他文件
        for other_file in skill_path.rglob("*"):
            if other_file.is_file() and other_file.suffix not in ['.py', '.json']:
                arcname = str(other_file.relative_to(skill_path))
                zf.write(other_file, arcname)
    
    print(f"✅ Skill 包已生成: {output_file}")
    print(f"   版本: {version}")
    print(f"   文件大小: {output_file.stat().st_size / 1024:.2f} KB")
    
    return str(output_file)


def install_skill(skill_file: str) -> bool:
    """
    安装 Skill 到 Trae 全局目录
    
    Args:
        skill_file: .skill 文件路径
    
    Returns:
        是否安装成功
    """
    skill_path = Path(skill_file)
    
    if not skill_path.exists():
        print(f"❌ 文件不存在: {skill_file}")
        return False
    
    # Trae 的全局 Skills 目录
    # 常见位置: ~/.trae/skills 或 ~/.config/trae/skills
    possible_dirs = [
        Path.home() / ".trae" / "skills",
        Path.home() / ".config" / "trae" / "skills",
        Path.home() / ".local" / "share" / "trae" / "skills"
    ]
    
    skill_dir = None
    for d in possible_dirs:
        if d.exists() or os.access(str(d.parent), os.W_OK):
            skill_dir = d
            break
    
    if not skill_dir:
        # 创建默认目录
        skill_dir = Path.home() / ".trae" / "skills"
        skill_dir.mkdir(parents=True, exist_ok=True)
    
    # 解压 Skill 包
    skill_name = skill_path.stem
    extract_dir = skill_dir / skill_name
    
    # 如果已存在，先删除
    if extract_dir.exists():
        import shutil
        shutil.rmtree(extract_dir)
    
    extract_dir.mkdir(parents=True)
    
    with zipfile.ZipFile(skill_path, 'r') as zf:
        zf.extractall(extract_dir)
    
    print(f"✅ Skill 已安装到: {extract_dir}")
    print(f"   位置: {skill_dir}")
    
    # 创建符号链接（如果需要）
    config_file = skill_dir.parent / "config.json"
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Skill 打包工具")
    parser.add_argument("--name", "-n", default="my_skill", help="Skill 名称")
    parser.add_argument("--output", "-o", default="./", help="输出目录")
    parser.add_argument("--install", "-i", action="store_true", help="安装到全局")
    parser.add_argument("--dir", "-d", default=None, help="Skill 目录路径")
    
    args = parser.parse_args()
    
    # 确定 Skill 目录
    if args.dir:
        skill_dir = args.dir
    else:
        # 默认为当前目录下的 skills/<name>
        script_dir = Path(__file__).parent
        skill_dir = script_dir / args.name
    
    try:
        # 创建包
        output_file = create_skill_package(str(skill_dir), args.output)
        
        # 如果需要安装
        if args.install:
            install_skill(output_file)
        
        print("\n📝 下一步:")
        print("   1. 在 Trae 中导入 Skill:")
        print(f"      - 打开设置 → Skills → 导入")
        print(f"      - 选择文件: {output_file}")
        print("")
        print("   2. 或手动解压到 Trae Skills 目录:")
        print(f"      - 复制 {output_file}")
        print(f"      - 到 ~/.trae/skills/")
        print("")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
