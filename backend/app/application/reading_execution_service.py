"""Compatibility projection for the existing reading-executions HTTP contract."""
from uuid import uuid4
from sqlalchemy import select
from app.models.execution import AgentExecution
from app.models.project import ProjectPaper
from app.application.research_orchestrator import ResearchOrchestrator


async def start_reading(db, project_id, user_id, max_items):
    rows = list((await db.scalars(select(ProjectPaper).where(ProjectPaper.project_id == project_id))).all())
    queued = [p for p in rows if (p.reading_plan or {}).get('status') in {'pending', 'reading', 'failed'}]
    queued.sort(key=lambda p: int((p.reading_plan or {}).get('order') or 9999))
    if not queued:
        raise ValueError('没有可执行的精读任务，请先选择论文')
    execution = AgentExecution(id=str(uuid4()), project_id=project_id, user_id=user_id,
        agent_type='research_goal', goal='精读选定项目论文', input_payload={
            'goal_type': 'READ_PAPERS', 'paper_ids': [p.paper_id for p in queued[:max_items]],
            'instruction': '分析核心贡献、方法、实验、证据与局限'}, status='queued')
    db.add(execution)
    await db.commit()
    await ResearchOrchestrator(db).initialize(execution)
    return await reading_projection(db, execution)


async def find_reading(db, execution_id, project_id, user_id):
    item = await db.get(AgentExecution, execution_id)
    if item and item.project_id == project_id and item.user_id == user_id and (item.plan or {}).get('goal', {}).get('goal_type') == 'READ_PAPERS':
        return item
    return None


async def reading_projection(db, execution):
    tasks = await ResearchOrchestrator(db).tasks(execution.id)
    results = [{'paper_id': next(r['artifact_id'] for r in t.input_refs if r['artifact_type'] == 'paper'),
                'status': 'completed'} for t in tasks if t.status == 'completed']
    current = next((t for t in tasks if t.status == 'running'), None)
    return {'task_id': execution.id, 'project_id': execution.project_id, 'user_id': execution.user_id,
        'status': execution.status, 'control': 'pause' if execution.status == 'paused' else 'run',
        'total': len(tasks), 'completed': len(results), 'results': results,
        'current_paper_id': next((r['artifact_id'] for r in current.input_refs if r['artifact_type'] == 'paper'), None) if current else None,
        'error': execution.error_message, 'created_at': execution.created_at.timestamp(), 'updated_at': execution.updated_at.timestamp()}
