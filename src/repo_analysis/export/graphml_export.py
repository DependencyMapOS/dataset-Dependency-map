from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _add_data(parent: ET.Element, key: str, text: str) -> None:
    el = ET.SubElement(parent, "data")
    el.set("key", key)
    el.text = text


def write_graphml(
    path: Path,
    *,
    graph_kind: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    commit_sha: str,
    tool_version: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
    keys = [
        ("node_id", "node", "string"),
        ("kind", "node", "string"),
        ("language", "node", "string"),
        ("source_path", "node", "string"),
        ("label", "node", "string"),
        ("commit_sha", "node", "string"),
        ("tool_version", "node", "string"),
        ("ext_json", "node", "string"),
        ("edge_kind", "edge", "string"),
        ("confidence", "edge", "string"),
        ("ext_json", "edge", "string"),
        ("graph_kind", "graph", "string"),
    ]
    for kid, fr, typ in keys:
        k = ET.SubElement(root, "key")
        k.set("id", kid)
        k.set("for", fr)
        k.set("attr.name", kid)
        k.set("attr.type", typ)

    graph = ET.SubElement(root, "graph")
    graph.set("edgedefault", "directed")
    _add_data(graph, "graph_kind", graph_kind)

    for n in sorted(nodes, key=lambda x: str(x.get("id", ""))):
        node = ET.SubElement(graph, "node")
        node.set("id", str(n["id"]))
        _add_data(node, "node_id", str(n["id"]))
        _add_data(node, "kind", str(n.get("kind", "")))
        _add_data(node, "language", str(n.get("language", "")))
        _add_data(node, "source_path", str(n.get("source_path", "")))
        _add_data(node, "label", str(n.get("label", "")))
        _add_data(node, "commit_sha", commit_sha)
        _add_data(node, "tool_version", tool_version)
        ext = n.get("ext_json")
        _add_data(node, "ext_json", ext if isinstance(ext, str) else "")

    for i, e in enumerate(sorted(edges, key=lambda x: (x["source"], x["target"], x["type"]))):
        edge = ET.SubElement(graph, "edge")
        edge.set("id", f"e{i}")
        edge.set("source", str(e["source"]))
        edge.set("target", str(e["target"]))
        _add_data(edge, "edge_kind", str(e.get("type", "")))
        conf = e.get("confidence")
        _add_data(edge, "confidence", "" if conf is None else str(conf))
        exte = e.get("ext_json")
        _add_data(edge, "ext_json", exte if isinstance(exte, str) else "")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)


def pydantic_to_graphml_nodes_edges_ast(model: BaseModel) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = model.model_dump()
    nodes_out: list[dict[str, Any]] = []
    edges_out: list[dict[str, Any]] = []
    for n in data.get("nodes", []):
        nodes_out.append(
            {
                "id": n["id"],
                "kind": n.get("kind", ""),
                "language": data.get("source_language", ""),
                "source_path": data.get("relative_path", ""),
                "label": n.get("label", ""),
                "ext_json": "",
            }
        )
    for e in data.get("edges", []):
        edges_out.append(
            {
                "source": e["source_id"],
                "target": e["target_id"],
                "type": e.get("type", ""),
                "confidence": None,
                "ext_json": "",
            }
        )
    return nodes_out, edges_out


def pydantic_to_graphml_nodes_edges_asg(model: BaseModel) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = model.model_dump()
    nodes_out: list[dict[str, Any]] = []
    edges_out: list[dict[str, Any]] = []
    for n in data.get("nodes", []):
        nodes_out.append(
            {
                "id": n["id"],
                "kind": n.get("kind", ""),
                "language": data.get("source_language", ""),
                "source_path": data.get("relative_path", ""),
                "label": n.get("label", ""),
                "ext_json": "",
            }
        )
    for e in data.get("edges", []):
        edges_out.append(
            {
                "source": e["source_id"],
                "target": e["target_id"],
                "type": e.get("type", ""),
                "confidence": e.get("confidence"),
                "ext_json": "",
            }
        )
    return nodes_out, edges_out
