"""数据库迁移脚本：为 sections 表添加 start_page 字段"""
import sqlite3

# 连接到数据库
conn = sqlite3.connect('/home/ddd/project/myAgent/backend/paperai.db')
cursor = conn.cursor()

try:
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(sections)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'start_page' not in columns:
        # 添加 start_page 字段
        cursor.execute("ALTER TABLE sections ADD COLUMN start_page INTEGER")
        print("✅ 成功添加 start_page 字段")
    else:
        print("ℹ️ start_page 字段已存在")
    
    conn.commit()
    print("✅ 数据库迁移完成")
    
except Exception as e:
    print(f"❌ 迁移失败: {e}")
    conn.rollback()
finally:
    conn.close()
