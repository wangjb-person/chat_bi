from chatbi.workflow.agent_workflow import AgentWorkflow


def test_should_fallback_when_all_tasks_failed():
    results = [
        {"task_id": "a", "error": "Unknown column", "dataframe": None},
        {"task_id": "b", "error": "no data", "dataframe": None},
    ]
    assert AgentWorkflow._should_fallback_to_knowledge(results) is True


def test_should_not_fallback_when_one_task_has_rows():
    import pandas as pd

    results = [
        {"task_id": "a", "error": "x", "dataframe": None},
        {"task_id": "b", "error": None, "dataframe": pd.DataFrame({"n": [1]})},
    ]
    assert AgentWorkflow._should_fallback_to_knowledge(results) is False
