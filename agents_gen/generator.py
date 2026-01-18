# generation_only.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from string import Template
from typing import Any, Mapping, Optional

import networkx as nx
from openai import OpenAI


# -------------------------
# Graph <-> JSON
# -------------------------
def graph_to_json(g: nx.DiGraph) -> dict:
    data: list[dict] = []
    for node_id in g.nodes:
        node_payload = dict(g.nodes[node_id])
        node_payload["id"] = node_id
        node_payload["to"] = []
        for next_id in g.adj[node_id].keys():
            edge_payload = dict(g.edges[(node_id, next_id)])
            edge_payload["id"] = next_id
            node_payload["to"].append(edge_payload)
        data.append(node_payload)
    return {"data": data}


def json_to_graph(structure: dict[str, Any]) -> nx.DiGraph:
    g = nx.DiGraph()

    # поддерживаем оба ключа: "data" (старый) и "nodes" (ваш)
    nodes = structure.get("data")
    if nodes is None:
        nodes = structure.get("nodes", [])

    for node in nodes:
        node_id = node["id"]

        node_attrs = dict(node)
        node_attrs.pop("to", None)
        g.add_node(node_id, **node_attrs)

        for child in node.get("to", []):
            child_id = child["id"]
            edge_attrs = dict(child)
            edge_attrs.pop("id", None)
            g.add_edge(node_id, child_id, **edge_attrs)

    return g

def graph_to_nodes_json(g: nx.DiGraph) -> dict:
    nodes = []
    for node_id in g.nodes:
        node_payload = dict(g.nodes[node_id])
        node_payload["id"] = node_id
        node_payload["to"] = []
        for next_id in g.adj[node_id].keys():
            edge_payload = dict(g.edges[(node_id, next_id)])
            edge_payload["id"] = next_id
            node_payload["to"].append(edge_payload)
        nodes.append(node_payload)
    return {"nodes": nodes}


# -------------------------
# Prompt rendering with checks
# -------------------------
_placeholder_re = re.compile(r"\$(?:\{(?P<braced>[a-zA-Z_]\w*)\}|(?P<plain>[a-zA-Z_]\w*))")


def required_placeholders(tpl: str) -> set[str]:
    return {m.group("braced") or m.group("plain") for m in _placeholder_re.finditer(tpl)}


def render_prompt_checked(tpl: str, ctx: Mapping[str, Any]) -> str:
    return Template(tpl).safe_substitute(**ctx)


# -------------------------
# Dialog chain helper
# -------------------------
def get_prev_dialog_chains(g: nx.DiGraph, node_id: int | str) -> list[str]:
    root = list(g.nodes)[0]
    paths = list(nx.all_simple_paths(g, source=root, target=node_id))
    chains: list[str] = []
    for path in paths:
        if len(path) < 2:
            continue
        # если ребро к target без line — цепочка не пригодна
        if not g.edges[path[-2], path[-1]].get("line"):
            continue

        s = ""
        for i in range(len(path) - 1):
            s += f"**NPC**: {g.nodes[path[i]].get('line','')}\n"
            s += f"**Игрок**: {g.edges[path[i], path[i+1]].get('line','')}\n"
        chains.append(s)
    return chains


# -------------------------
# Prompts container (generation only)
# -------------------------
@dataclass(frozen=True)
class GenerationPrompts:
    structure: str
    node_content: str
    edge_content: str


# -------------------------
# Generator-only pipeline
# -------------------------
class DialogGenerator:
    """
    Только генерация:
    1) generate_structure -> json
    2) generate_content -> заполняет line у нод и рёбер

    base_prompt_vars — словарь, который вы заводите/редактируете в ноутбуке.
    """

    def __init__(
        self,
        client: OpenAI,
        llm_settings: Any,
        params: dict[str, Any],
        *,
        model_structure: str,
        model_dialogue: str,
        max_tokens_structure: int = 8192,
        max_tokens_dialogue: int = 8192,
        system_prompt: str = "",
        prompts: Optional[GenerationPrompts] = None,
    ):
        self.client = client
        self.model_structure = model_structure
        self.model_dialogue = model_dialogue
        self.max_tokens_structure = max_tokens_structure
        self.max_tokens_dialogue = max_tokens_dialogue
        self.system_prompt = system_prompt
        self.prompts = prompts
        self.llm_settings = llm_settings

        self.params = params                # <-- ДОБАВИТЬ

        self.npc = params["npc"]            # <-- ДОБАВИТЬ
        self.hero = params["hero"]          # <-- ДОБАВИТЬ
        self.goals = params.get("goals", "")

        if self.prompts is None:
            raise ValueError("prompts is required (GenerationPrompts)")

    def _common_ctx(self) -> dict[str, Any]:
        return dict(
            json_structure=self.llm_settings.get_structure(),
            json_node_structure=self.llm_settings.get_node_structure(),
            json_edge_structure=self.llm_settings.get_edge_structure(),
            moods_list=self.llm_settings.get_moods(),
            json_tematics=self.llm_settings.get_json_tematics(),
            NPC_name=self.npc["name"],
            NPC_talk_style=self.npc["talk_style"],
            NPC_profession=self.npc["profession"],
            NPC_look=self.npc["look"],
            NPC_traits=self.npc["traits"],
            NPC_extra=self.npc["extra"],
            hero_name=self.hero["name"],
            hero_talk_style=self.hero["talk_style"],
            hero_profession=self.hero["profession"],
            hero_look=self.hero["look"],
            hero_traits=self.hero["traits"],
            hero_extra=self.hero["extra"],
            NPC_to_hero_relation=self.params["NPC_to_hero_relation"],
            hero_to_NPC_relation=self.params["hero_to_NPC_relation"],
            world_settings=self.params["world_settings"],
            scene=self.params["scene"],
            genre=self.params["genre"],
            epoch=self.params["epoch"],
            tonality=self.params["tonality"],
            extra=self.params["extra"],
            context=self.params["context"],
            mx_answers_cnt=self.params["mx_answers_cnt"],
            mn_answers_cnt=self.params["mn_answers_cnt"],
            mx_depth=self.params["mx_depth"],
            mn_depth=self.params["mn_depth"],
            goals=self.goals,
            items_dict=self.params.get("items_dict", {}),
        )
    def generate_structure(self) -> dict:
        prompt = render_prompt_checked(self.prompts.structure, self._common_ctx())
        print(prompt)
        resp = self.client.chat.completions.create(
            model=self.model_structure,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            max_tokens=self.max_tokens_structure,
            response_format={"type": "json_object"},
        )
        print(resp.choices[0].message.content)
        return json.loads(resp.choices[0].message.content)

    def generate_content(self, g: nx.DiGraph) -> nx.DiGraph:
        from collections import deque

        q = deque()
        print(g)
        root = list(g.nodes)[0]
        q.append(root)
        used: list[int | str] = []

        while q:
            t = q.popleft()
            used.append(t)

            prev_chains = get_prev_dialog_chains(g, t)
            next_nodes = list(g.adj[t].keys())

            # -------- node (NPC) line
            node_ctx = dict(self._common_ctx())
            node_ctx.update(
                {
                    "chain": "\n = = = = \n".join(prev_chains),
                    "tematic": g.nodes[t].get("info", ""),
                    "mood": g.nodes[t].get("mood", ""),
                }
            )
            prompt_node = render_prompt_checked(self.prompts.node_content, node_ctx)

            node_resp = self.client.chat.completions.create(
                model=self.model_dialogue,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt_node},
                ],
                stream=False,
                max_tokens=self.max_tokens_dialogue,
            )
            g.nodes[t]["line"] = node_resp.choices[0].message.content.strip("\"\'")

            # дописываем NPC реплику в цепочки
            for i in range(len(prev_chains)):
                prev_chains[i] += f"**NPC**: {g.nodes[t]['line']}\n"

            # -------- edges (Hero) lines for outgoing edges
            if next_nodes:
                tematics = {
                    "tematics": [
                        {
                            "id": n,
                            "info": g.nodes[n].get("info", ""),
                            "mood": g.edges[t, n].get("mood", ""),
                        }
                        for n in next_nodes
                    ]
                }

                edge_ctx = dict(self._common_ctx())
                edge_ctx.update(
                    {
                        "chain": "\n = = = = \n".join(prev_chains),
                        "tematics": tematics,
                        "replic_cnt": len(tematics["tematics"]),
                        "mood": g.nodes[t].get("mood", ""),
                    }
                )
                prompt_edge = render_prompt_checked(self.prompts.edge_content, edge_ctx)

                edge_resp = self.client.chat.completions.create(
                    model=self.model_dialogue,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt_edge},
                    ],
                    stream=False,
                    max_tokens=self.max_tokens_dialogue,
                    response_format={"type": "json_object"},
                )

                lines = json.loads(edge_resp.choices[0].message.content)["lines"]

                for line_obj in lines:
                    to_id = int(line_obj["id"])
                    for k, v in line_obj.items():
                        if k == "id":
                            continue
                        g.edges[t, to_id][k] = v.strip("\"\'") if isinstance(v, str) else v

            # BFS
            for n in next_nodes:
                if n not in used and n not in q:
                    q.append(n)

        return g

    def run(self) -> dict:
        structure = self.generate_structure()
        g = json_to_graph(structure)
        self.generate_content(g)
        return graph_to_json(g)
