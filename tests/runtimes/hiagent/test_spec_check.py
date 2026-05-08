import pytest

from loom.runtimes.hiagent.spec_check import (
    HiagentSpecError,
    check_generated_chatflow_config,
    check_materialized_chatflow_nodes,
)


def test_spec_check_catches_missing_raw_output():
    with pytest.raises(HiagentSpecError, match="raw_output"):
        check_generated_chatflow_config({
            "Nodes": [
                {
                    "Type": "LLM",
                    "Configs": {
                        "LLM": {
                            "OutputSchema": [{"Name": "answer", "Required": True, "Type": 0}]
                        }
                    },
                }
            ]
        })


def test_spec_check_rejects_knowledgebase_typename():
    with pytest.raises(HiagentSpecError, match="Knowledge"):
        check_generated_chatflow_config({
            "Nodes": [
                {
                    "Type": "KnowledgeBase",
                    "Configs": {"KnowledgeBase": {"KnowledgeIDs": [], "Similarity": 0.5}},
                }
            ]
        })


def test_intent_node_has_class_other_branch():
    with pytest.raises(HiagentSpecError, match="class_other"):
        check_generated_chatflow_config({
            "Nodes": [
                {
                    "Type": "Intent",
                    "Configs": {
                        "Intent": {
                            "Intentions": [
                                {"Name": "refund", "Description": "refund", "PortID": "class01"}
                            ],
                            "QueryVariable": {"Name": "query", "RefType": "sys", "Path": "query"},
                        }
                    },
                }
            ]
        })


def test_end_node_output_type_variable_has_node_code():
    with pytest.raises(HiagentSpecError, match="NodeCode"):
        check_materialized_chatflow_nodes([
            {"Type": "Start", "Code": "start", "NodeConfig": {"StartNode": _start_config()}},
            {
                "Type": "End",
                "Code": "end",
                "NodeConfig": {
                    "EndNode": {
                        "OutputType": "Variable",
                        "Input": [{"Name": "answer", "RefType": "node_field", "Path": "raw_output"}],
                    }
                },
            },
        ])


def test_spec_check_accepts_materialized_valid_shape():
    check_materialized_chatflow_nodes([
        {"Type": "Start", "Code": "start", "NodeConfig": {"StartNode": _start_config()}},
        {
            "Type": "LLM",
            "Code": "llm",
            "NodeConfig": {
                "LLMNode": {
                    "OutputSchema": [{"Name": "raw_output", "Required": True, "Type": 0}],
                    "Input": [
                        {
                            "Name": "query",
                            "RefType": "node_field",
                            "Path": "query",
                            "NodeCode": "start",
                        }
                    ],
                }
            },
        },
        {"Type": "End", "Code": "end", "NodeConfig": {"EndNode": {"OutputType": "Content"}}},
    ])


def _start_config() -> dict[str, list[dict[str, object]]]:
    fields = [
        {"Name": "query", "Type": 0},
        {"Name": "files", "Type": 11},
        {"Name": "chat_histories", "Type": 9},
    ]
    return {"InputSchema": fields, "OutputSchema": fields}
