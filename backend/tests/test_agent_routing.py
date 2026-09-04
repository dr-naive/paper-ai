from app.harness.agents.routing import (
    ExecutionMode,
    ProjectAction,
    decide_agent_route,
    detect_project_action,
)


def test_project_memory_word_variants_route_to_react():
    questions = [
        "请帮我写入一条记忆：用户更关注推理速度",
        "把这个结论记到项目记忆里",
        "记录一下这个调研要点",
    ]
    for question in questions:
        decision = decide_agent_route(question, project_id="project-1")
        assert decision.mode is ExecutionMode.REACT
        assert decision.project_action is ProjectAction.WRITE_MEMORY


def test_project_actions_are_not_enabled_without_project_scope():
    decision = decide_agent_route("记录一下这个调研要点")
    assert decision.mode is ExecutionMode.FAST
    assert decision.project_action is ProjectAction.NONE


def test_project_read_and_library_actions_are_classified():
    assert detect_project_action("回顾一下之前记录的调研进展") is ProjectAction.READ_MEMORY
    assert detect_project_action("把这篇论文加入项目文档库") is ProjectAction.MANAGE_LIBRARY
    assert detect_project_action("生成一份文献综述") is ProjectAction.SAVE_ARTIFACT


def test_critique_and_deep_analysis_use_react():
    assert decide_agent_route("请写一份审稿意见").reason == "critique_requires_subagent"
    decision = decide_agent_route(
        "为什么这个方法有效？", intent_type="analytical", complexity="high"
    )
    assert decision.mode is ExecutionMode.REACT
    assert decision.reason == "deep_analysis"


def test_simple_project_question_keeps_fast_path():
    decision = decide_agent_route(
        "这篇论文用了什么数据集？", project_id="project-1", intent_type="factual"
    )
    assert decision.mode is ExecutionMode.FAST


def test_medium_project_analysis_uses_react():
    decision = decide_agent_route(
        "比较这两个实验设置", project_id="project-1", intent_type="analytical", complexity="medium"
    )
    assert decision.mode is ExecutionMode.REACT
    assert decision.reason == "project_analysis"


def test_cross_paper_factual_question_uses_project_retrieval():
    decision = decide_agent_route(
        "这些论文分别使用了哪些数据集？",
        project_id="project-1",
        intent_type="factual",
        complexity="medium",
    )
    assert decision.mode is ExecutionMode.REACT
    assert decision.project_action is ProjectAction.RESEARCH


def test_topic_selection_routes_to_domain_mapping():
    for question in ("帮我做领域地图", "这个方向有哪些研究空白？", "帮我确定论文选题"):
        decision = decide_agent_route(question, project_id="project-1")
        assert decision.mode is ExecutionMode.REACT
        assert decision.project_action is ProjectAction.MAP_DOMAIN


def test_reading_plan_routes_to_project_agent():
    decision = decide_agent_route("根据领域地图安排精读计划", project_id="project-1")
    assert decision.mode is ExecutionMode.REACT
    assert decision.project_action is ProjectAction.PLAN_READING


def test_evidence_matrix_routes_to_project_agent():
    decision = decide_agent_route("生成跨论文证据矩阵并找冲突结论", project_id="project-1")
    assert decision.mode is ExecutionMode.REACT
    assert decision.project_action is ProjectAction.BUILD_EVIDENCE_MATRIX


def test_experiment_design_routes_to_project_agent():
    decision = decide_agent_route("根据证据设计可证伪假设和消融实验", project_id="project-1")
    assert decision.mode is ExecutionMode.REACT
    assert decision.project_action is ProjectAction.DESIGN_EXPERIMENT


def test_writing_blueprint_and_draft_routes_are_distinct():
    assert detect_project_action("生成论文写作蓝图") is ProjectAction.PLAN_WRITING
    assert detect_project_action("撰写方法章节草稿") is ProjectAction.DRAFT_SECTION


def test_audit_and_finalize_routes_are_distinct():
    assert detect_project_action("对全文做引用审计和事实核查") is ProjectAction.AUDIT_DRAFT
    assert detect_project_action("审计通过后生成终稿") is ProjectAction.FINALIZE_MANUSCRIPT
