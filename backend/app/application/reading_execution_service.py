"""Compatibility adapter for the existing project Reading HTTP contract."""
from uuid import uuid4

from sqlalchemy import select

from app.application.execution_service import execution_dict
from app.application.project_execution_entrypoint import initialize_project_goal, is_project_goal_execution
from app.models.execution import AgentExecution
from app.models.project import ProjectPaper


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
    await initialize_project_goal(db, execution)
    return await reading_projection(db, execution)


async def find_reading(db, execution_id, project_id, user_id):
    item = await db.get(AgentExecution, execution_id)
    if item and item.project_id == project_id and item.user_id == user_id and is_project_goal_execution(item) \
            and (item.plan or {}).get('goal', {}).get('goal_type') == 'READ_PAPERS':
        return item
    return None


async def reading_projection(db, execution):
    from app.application.research_orchestrator import ResearchOrchestrator

    tasks = await ResearchOrchestrator(db).tasks(execution.id)
    results = []
    for task in tasks:
        paper_ref = next((r for r in task.input_refs if r.get('artifact_type') == 'paper'), None)
        if paper_ref and task.status == 'completed':
            results.append({'paper_id': paper_ref['artifact_id'], 'status': 'completed'})
    current = next((t for t in tasks if t.status == 'running'), None)
    current_paper = next((r for r in (current.input_refs if current else []) if r.get('artifact_type') == 'paper'), None)
    payload = execution_dict(execution)
    payload.update({
        'task_id': execution.id,
        'control': 'pause' if execution.status == 'paused' else 'run',
        'total': len(tasks),
        'completed': len(results),
        'results': results,
        'current_paper_id': current_paper.get('artifact_id') if current_paper else None,
        'error': execution.error_message,
        # Preserve the old reading-executions timestamp shape while exposing
        # the full GoalExecution progress/blocker/result projection above.
        'created_at': execution.created_at.timestamp(),
        'updated_at': execution.updated_at.timestamp(),
    })
    return payload
