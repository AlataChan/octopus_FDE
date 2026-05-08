"""Hiagent API push command."""
from __future__ import annotations

import json
import os
import sys
import webbrowser
from pathlib import Path

import click

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.api_client import HiagentAPIClient, HiagentAPIError
from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError
from loom.runtimes.hiagent.spec_check import check_materialized_chatflow_nodes
from loom.runtimes.hiagent.v2_6.compiler import (
    build_agent_config_draft,
    build_agent_config_request,
    build_chatflow_config_draft,
)


@click.group(help="Hiagent self-hosted API operations.")
def hiagent() -> None:
    pass


@hiagent.command(help="Push IR as a Hiagent app via the TOP API.")
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--binding",
    "binding_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("config/customers/bambu.hiagent.yaml"),
    show_default=True,
    help="Customer Binding YAML.",
)
@click.option("--name", help="Hiagent app name. Defaults to IR metadata.name.")
@click.option("--description", default="", help="Hiagent app description.")
@click.option("--version", "version_name", default="v1.0.0", show_default=True)
@click.option(
    "--mode",
    type=click.Choice(["single", "chatflow"]),
    default="single",
    show_default=True,
    help="single collapses to a chat agent; chatflow preserves the IR graph.",
)
@click.option("--auto-open", is_flag=True, help="Open the Hiagent agent URL after publish.")
def push(
    ir_file: Path,
    binding_path: Path,
    name: str | None,
    description: str,
    version_name: str,
    mode: str,
    auto_open: bool,
) -> None:
    try:
        ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
        agent_name = name or ir.metadata.name
        agent_description = description or ir.metadata.description or ir.metadata.name
        binding = HiagentBinding.load(binding_path)
        client = HiagentAPIClient.from_env()
        click.echo("Checking app name...")
        if client.check_app_by_name(agent_name):
            click.echo(f"Hiagent app already exists: {agent_name}", err=True)
            sys.exit(2)
        click.echo("Creating app...")
        app_id = client.create_app(
            name=agent_name,
            app_type="ChatFlow" if mode == "chatflow" else "Chat",
            description=agent_description,
        )
        binding = _binding_with_model_defaults(ir, binding, client)
        if mode == "chatflow":
            chatflow_config = build_chatflow_config_draft(ir, binding)
            click.echo("Creating chatflow graph nodes...")
            chatflow_config = _materialize_chatflow_graph(client, app_id, chatflow_config)
            click.echo("Saving chatflow config draft...")
            client.save_chatflow_config_draft(app_id, chatflow_config)
            click.echo("Publishing...")
            publish_id = client.publish_app_v2(
                app_id,
                chatflow_config=chatflow_config,
                agent_mode="",
                version=version_name,
            )
        else:
            draft = build_agent_config_draft(ir, binding)
            publish_config = build_agent_config_request(ir, binding)
            click.echo("Saving draft...")
            client.save_app_config_draft(app_id, draft)
            click.echo("Publishing...")
            publish_id = client.publish_app_v2(
                app_id,
                app_config=publish_config,
                version=version_name,
            )
    except (HiagentAPIError, HiagentBindingError, ValueError) as e:
        click.echo(f"Hiagent push failed: {e}", err=True)
        sys.exit(2)

    url = client.app_url(app_id)
    click.echo("")
    click.echo(click.style("✓ Agent created and published", fg="green"))
    click.echo("")
    click.echo(f"  Name:       {agent_name}")
    click.echo(f"  Mode:       {mode}")
    click.echo(f"  Workspace:  {client.workspace_id}")
    click.echo(f"  Agent ID:   {app_id}")
    click.echo(f"  Version:    {publish_id}")
    click.echo(f"  URL:        {click.style(url, fg='blue', underline=True)}")
    click.echo("")
    click.echo("Next: open the URL above to chat with your agent in Hiagent UI.")
    if auto_open:
        _open_browser(url)


def _binding_with_model_defaults(
    ir: IRDocument,
    binding: HiagentBinding,
    client: HiagentAPIClient,
) -> HiagentBinding:
    handles = _model_handles(ir)
    missing = [handle for handle in handles if not binding.resolve_model(handle)]
    if not missing:
        return binding

    model_id = client.resolve_default_text_generation_model_id()
    if not model_id:
        raise HiagentAPIError(
            "no text-generation model is granted to the workspace; set HIAGENT_MODEL_ID "
            "or fill model_id_map in the Hiagent binding"
        )
    model_id_map = {**binding.model_id_map}
    for handle in missing:
        model_id_map[handle] = model_id
    binding = binding.model_copy(update={"model_id_map": model_id_map})

    missing_datasets = [
        dataset
        for dataset in ir.registry_ref.datasets
        if not binding.resolve_dataset(dataset)
    ]
    if not missing_datasets:
        return binding
    dataset_id = client.resolve_default_dataset_id()
    if not dataset_id:
        raise HiagentAPIError(
            "no knowledge dataset is available to the workspace; set HIAGENT_DATASET_ID "
            "or fill dataset_id_map in the Hiagent binding"
        )
    dataset_id_map = {**binding.dataset_id_map}
    for handle in missing_datasets:
        dataset_id_map[handle] = dataset_id
    return binding.model_copy(update={"dataset_id_map": dataset_id_map})


def _model_handles(ir: IRDocument) -> list[str]:
    out: list[str] = []
    for node in ir.nodes:
        model = getattr(node, "model", None)
        if isinstance(model, str) and model and model not in out:
            out.append(model)
    return out


def _materialize_chatflow_graph(
    client: HiagentAPIClient,
    app_id: str,
    chatflow_config: dict[str, object],
) -> dict[str, object]:
    """Create server-side ChatFlow nodes, then save links for the graph.

    Hiagent rejects arbitrary client-generated node IDs in SaveChatflow. A
    freshly-created ChatFlow app already has Start/End nodes; all other nodes
    must be created through CreateChatFlowNode so the server issues valid IDs.
    """
    generated_nodes = _as_node_list(chatflow_config["Nodes"])
    graph = client.get_chatflow(app_id, with_node=True)
    default_nodes = _as_node_list(graph.get("Nodes", []))
    reusable = _default_node_pool(default_nodes)
    server_by_generated_code: dict[str, dict[str, object]] = {}
    server_nodes: list[dict[str, object]] = []
    first_end_node: dict[str, object] | None = None

    for node in generated_nodes:
        api_type = _chatflow_api_node_type(str(node["Type"]))
        if api_type == "End" and first_end_node is not None:
            server_node = first_end_node
        else:
            reusable_node = _pop_reusable_node(reusable, api_type)
            if reusable_node is None:
                server_node = client.create_chatflow_node(
                    app_id,
                    node_type=api_type,
                    layout=_as_layout(node["Layout"]),
                    name=str(node["Name"]),
                )
            else:
                server_node = {
                    **reusable_node,
                    "Layout": _as_layout(node["Layout"]),
                    "Name": str(node["Name"]),
                }
            if api_type == "End":
                first_end_node = server_node
        _patch_chatflow_node_config(server_node, node)
        server_by_generated_code[str(node["Code"])] = server_node
        if not any(existing.get("Code") == server_node.get("Code") for existing in server_nodes):
            server_nodes.append(server_node)

    links = _server_links(generated_nodes, server_by_generated_code)
    _normalize_sys_refs(server_nodes)
    check_materialized_chatflow_nodes(server_nodes)
    client.save_chatflow(app_id, nodes=server_nodes, links=links)
    flow_id = _flow_id(server_nodes) or app_id
    return {
        **chatflow_config,
        "ID": flow_id,
        "UniqueName": flow_id,
        "WorkflowID": flow_id,
        "Nodes": server_nodes,
    }


def _as_node_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("ChatFlow graph expected a list of nodes")
    return [node for node in value if isinstance(node, dict)]


def _as_layout(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {"X": 0.0, "Y": 0.0}


def _default_node_pool(nodes: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    pool: dict[str, list[dict[str, object]]] = {}
    for node in nodes:
        typ = node.get("Type")
        if isinstance(typ, str):
            pool.setdefault(typ, []).append(node)
    return pool


def _pop_reusable_node(
    pool: dict[str, list[dict[str, object]]],
    node_type: str,
) -> dict[str, object] | None:
    nodes = pool.get(node_type)
    if nodes:
        return nodes.pop(0)
    return None


def _chatflow_api_node_type(type_name: str) -> str:
    return {
        "KnowledgeBase": "Knowledge",
        "Knowledge": "Knowledge",
        "HTTPRequest": "Tool",
    }.get(type_name, type_name)


def _server_links(
    generated_nodes: list[dict[str, object]],
    server_by_generated_code: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    generated_by_code = {str(node["Code"]): node for node in generated_nodes}
    intent_port_index: dict[str, int] = {}
    for node in generated_nodes:
        to_node = server_by_generated_code.get(str(node["Code"]))
        if to_node is None:
            continue
        depends = node.get("Depends", [])
        if not isinstance(depends, list):
            continue
        for dep in depends:
            if not isinstance(dep, dict):
                continue
            from_node = server_by_generated_code.get(str(dep.get("NodeCode", "")))
            if from_node is None:
                continue
            from_port: dict[str, object] = {"NodeCode": from_node["Code"]}
            source_generated = generated_by_code.get(str(dep.get("NodeCode", "")))
            if source_generated and source_generated.get("Type") == "Intent":
                source_code = str(source_generated["Code"])
                port_index = intent_port_index.get(source_code, 0)
                if to_node.get("Type") == "Code":
                    from_port["PortID"] = f"class{port_index + 1:02d}"
                    intent_port_index[source_code] = port_index + 1
                else:
                    from_port["PortID"] = "class_other"
            links.append({
                "From": from_port,
                "To": {"NodeCode": to_node["Code"]},
            })
    return links


def _normalize_sys_refs(nodes: list[dict[str, object]]) -> None:
    start_code = next(
        (str(node["Code"]) for node in nodes if node.get("Type") == "Start" and node.get("Code")),
        "",
    )
    if not start_code:
        return
    for node in nodes:
        _replace_sys_refs(node, start_code)


def _replace_sys_refs(value: object, start_code: str) -> None:
    if isinstance(value, dict):
        if value.get("RefType") == "sys":
            field = _default_start_field(value.get("Path"), value.get("Name"))
            value["RefType"] = "node_field"
            value["NodeCode"] = start_code
            value["Name"] = field
            value["Path"] = field
        elif value.get("RefType") == "node_field" and value.get("NodeCode") == start_code:
            field = _default_start_field(value.get("Path"), value.get("Name"))
            value["Name"] = field
            value["Path"] = field
        for child in value.values():
            _replace_sys_refs(child, start_code)
    elif isinstance(value, list):
        for child in value:
            _replace_sys_refs(child, start_code)


def _patch_chatflow_node_config(
    server_node: dict[str, object],
    generated_node: dict[str, object],
) -> None:
    configs = generated_node.get("Configs")
    if not isinstance(configs, dict):
        return
    generated_type = str(generated_node["Type"])
    if generated_type == "Start":
        return
    elif generated_type in {"Knowledge", "KnowledgeBase"}:
        knowledge = configs.get("Knowledge") or configs.get("KnowledgeBase")
        if isinstance(knowledge, dict):
            _set_node_config(
                server_node,
                "KnowledgeNode",
                {
                    "QueryVariable": knowledge.get("QueryVariable"),
                    "Knowledges": knowledge.get("KnowledgeIDs", []),
                    "TopK": knowledge.get("TopK", 3),
                    "ScoreThreshold": max(float(knowledge.get("Similarity") or 0.5), 0.01),
                    "RetrievalSearchMethod": 0,
                    "Expand": False,
                },
            )
    elif generated_type == "LLM":
        llm = configs.get("LLM")
        if isinstance(llm, dict):
            _set_node_config(
                server_node,
                "LLMNode",
                {
                    "ModelID": llm.get("ModelID", ""),
                    "Temperature": llm.get("Temperature", 0.7),
                    "TopP": 0.9,
                    "MaxTokens": min(int(llm.get("MaxTokens") or 4096), 4096),
                    "SystemPrompt": llm.get("SystemPrompt", ""),
                    "Prompt": llm.get("Prompt", ""),
                    "Input": [llm["QueryVariable"]] if llm.get("QueryVariable") else [],
                    "OutputFormat": "json",
                    "OutputSchema": llm.get("OutputSchema", []),
                    "TimeoutSeconds": llm.get("TimeoutSeconds", 120),
                    "Retries": llm.get("Retries", 0),
                },
            )
    elif generated_type == "Intent":
        intent = configs.get("Intent")
        if isinstance(intent, dict):
            _set_node_config(
                server_node,
                "IntentNode",
                {
                    **intent,
                    "QueryVariable": intent.get("QueryVariable") or {
                        "Name": "query",
                        "RefType": "sys",
                        "Path": "query",
                    },
                },
            )
    elif generated_type == "Code":
        _set_node_config(server_node, "CodeNode", configs.get("Code"))
    elif generated_type == "End":
        end = configs.get("End")
        if isinstance(end, dict):
            _set_node_config(
                server_node,
                "EndNode",
                {
                    "OutputType": "Content",
                    "Template": end.get("Template", ""),
                    "StreamOutput": end.get("StreamOutput", True),
                },
            )


def _set_node_config(
    server_node: dict[str, object],
    key: str,
    value: object,
) -> None:
    if isinstance(value, dict):
        server_node["NodeConfig"] = {key: value}


def _default_start_field(path: object, name: object = "") -> str:
    raw = str(path or name or "query").strip()
    head = raw.replace("[", ".").split(".", 1)[0].lower().replace("-", "_")
    if head in {
        "file",
        "files",
        "attachment",
        "attachments",
    }:
        return "files"
    if head in {
        "chat_history",
        "chat_histories",
        "conversation",
        "conversations",
        "history",
        "histories",
    }:
        return "chat_histories"
    if head in {
        "query",
        "user_query",
        "user_question",
        "question",
        "message",
        "input",
        "text",
        "user_input",
        "prompt",
    }:
        return "query"
    return "query"


def _flow_id(nodes: list[dict[str, object]]) -> str | None:
    for node in nodes:
        flow_id = node.get("FlowID")
        if isinstance(flow_id, str) and flow_id:
            return flow_id
    return None


def _open_browser(url: str) -> None:
    """Open a browser without leaking platform launcher diagnostics to CLI output."""
    with open(os.devnull, "w") as devnull:
        old_stdout = os.dup(1)
        old_stderr = os.dup(2)
        try:
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            opened = webbrowser.open(url)
        finally:
            os.dup2(old_stdout, 1)
            os.dup2(old_stderr, 2)
            os.close(old_stdout)
            os.close(old_stderr)
    if not opened:
        click.echo("Note: --auto-open requested, but no local browser accepted the URL.", err=True)
