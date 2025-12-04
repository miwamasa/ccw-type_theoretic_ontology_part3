"""
PROV-O準拠の来歴（Provenance）記録システム

W3C PROV-O (https://www.w3.org/TR/prov-o/) に基づいて、
型合成システムの計算過程を来歴グラフとして記録する。

主要な概念:
- Entity: データやオブジェクト（入力値、中間結果、出力値）
- Activity: エンティティを生成・使用・変更する活動（関数適用）
- Agent: アクティビティに責任を持つ主体（システム、ユーザー）

主要な関係:
- wasGeneratedBy: エンティティがアクティビティによって生成された
- used: アクティビティがエンティティを使用した
- wasAttributedTo: エンティティがエージェントに帰属する
- wasAssociatedWith: アクティビティがエージェントと関連付けられている
- wasDerivedFrom: エンティティが別のエンティティから派生した
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json
import uuid


@dataclass
class Entity:
    """PROV-O Entity: データやオブジェクト"""
    id: str
    type_name: str
    value: Any
    attributes: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "Entity",
            "prov:type": self.type_name,
            "value": str(self.value),
            "attributes": self.attributes,
            "prov:generatedAtTime": self.timestamp
        }


@dataclass
class Activity:
    """PROV-O Activity: エンティティを生成・使用・変更する活動"""
    id: str
    func_id: str
    func_signature: str
    start_time: str
    end_time: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "type": "Activity",
            "func_id": self.func_id,
            "func_signature": self.func_signature,
            "prov:startedAtTime": self.start_time,
            "attributes": self.attributes
        }
        if self.end_time:
            result["prov:endedAtTime"] = self.end_time
        return result


@dataclass
class Agent:
    """PROV-O Agent: アクティビティに責任を持つ主体"""
    id: str
    name: str
    agent_type: str  # "system", "user", "service"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "Agent",
            "name": self.name,
            "agent_type": self.agent_type,
            "attributes": self.attributes
        }


@dataclass
class Usage:
    """PROV-O used: アクティビティがエンティティを使用"""
    activity_id: str
    entity_id: str
    role: str = ""  # "input", "parameter", etc.
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Generation:
    """PROV-O wasGeneratedBy: エンティティがアクティビティによって生成"""
    entity_id: str
    activity_id: str
    role: str = ""  # "output", "result", etc.
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Derivation:
    """PROV-O wasDerivedFrom: エンティティが別のエンティティから派生"""
    derived_entity_id: str
    source_entity_id: str
    activity_id: Optional[str] = None
    derivation_type: str = "Derivation"  # "Derivation", "Revision", "Quotation"


@dataclass
class Association:
    """PROV-O wasAssociatedWith: アクティビティがエージェントと関連付けられている"""
    activity_id: str
    agent_id: str
    role: str = ""


@dataclass
class Attribution:
    """PROV-O wasAttributedTo: エンティティがエージェントに帰属"""
    entity_id: str
    agent_id: str


class ProvenanceGraph:
    """来歴グラフ: PROV-Oデータモデルを管理"""

    def __init__(self, namespace: str = "http://example.org/provenance/"):
        self.namespace = namespace
        self.entities: Dict[str, Entity] = {}
        self.activities: Dict[str, Activity] = {}
        self.agents: Dict[str, Agent] = {}
        self.usages: List[Usage] = []
        self.generations: List[Generation] = []
        self.derivations: List[Derivation] = []
        self.associations: List[Association] = []
        self.attributions: List[Attribution] = []

        # デフォルトのシステムエージェントを追加
        self.system_agent = self.add_agent(
            agent_id="system",
            name="TypeSynthesis System",
            agent_type="system",
            attributes={"version": "1.0"}
        )

    def _generate_id(self, prefix: str) -> str:
        """一意なIDを生成"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def add_entity(
        self,
        entity_id: Optional[str],
        type_name: str,
        value: Any,
        attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        """エンティティを追加"""
        if entity_id is None:
            entity_id = self._generate_id("entity")

        entity = Entity(
            id=entity_id,
            type_name=type_name,
            value=value,
            attributes=attributes or {}
        )
        self.entities[entity_id] = entity
        return entity_id

    def add_activity(
        self,
        activity_id: Optional[str],
        func_id: str,
        func_signature: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        """アクティビティを追加"""
        if activity_id is None:
            activity_id = self._generate_id("activity")

        activity = Activity(
            id=activity_id,
            func_id=func_id,
            func_signature=func_signature,
            start_time=datetime.now().isoformat(),
            attributes=attributes or {}
        )
        self.activities[activity_id] = activity
        return activity_id

    def end_activity(self, activity_id: str):
        """アクティビティを終了"""
        if activity_id in self.activities:
            self.activities[activity_id].end_time = datetime.now().isoformat()

    def add_agent(
        self,
        agent_id: Optional[str],
        name: str,
        agent_type: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        """エージェントを追加"""
        if agent_id is None:
            agent_id = self._generate_id("agent")

        agent = Agent(
            id=agent_id,
            name=name,
            agent_type=agent_type,
            attributes=attributes or {}
        )
        self.agents[agent_id] = agent
        return agent_id

    def add_usage(self, activity_id: str, entity_id: str, role: str = ""):
        """使用関係を追加"""
        self.usages.append(Usage(
            activity_id=activity_id,
            entity_id=entity_id,
            role=role
        ))

    def add_generation(self, entity_id: str, activity_id: str, role: str = ""):
        """生成関係を追加"""
        self.generations.append(Generation(
            entity_id=entity_id,
            activity_id=activity_id,
            role=role
        ))

    def add_derivation(
        self,
        derived_entity_id: str,
        source_entity_id: str,
        activity_id: Optional[str] = None
    ):
        """派生関係を追加"""
        self.derivations.append(Derivation(
            derived_entity_id=derived_entity_id,
            source_entity_id=source_entity_id,
            activity_id=activity_id
        ))

    def add_association(self, activity_id: str, agent_id: str, role: str = ""):
        """関連付け関係を追加"""
        self.associations.append(Association(
            activity_id=activity_id,
            agent_id=agent_id,
            role=role
        ))

    def add_attribution(self, entity_id: str, agent_id: str):
        """帰属関係を追加"""
        self.attributions.append(Attribution(
            entity_id=entity_id,
            agent_id=agent_id
        ))

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "namespace": self.namespace,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "activities": {k: v.to_dict() for k, v in self.activities.items()},
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "usages": [
                {
                    "activity": u.activity_id,
                    "entity": u.entity_id,
                    "role": u.role,
                    "time": u.timestamp
                }
                for u in self.usages
            ],
            "generations": [
                {
                    "entity": g.entity_id,
                    "activity": g.activity_id,
                    "role": g.role,
                    "time": g.timestamp
                }
                for g in self.generations
            ],
            "derivations": [
                {
                    "derived": d.derived_entity_id,
                    "source": d.source_entity_id,
                    "activity": d.activity_id,
                    "type": d.derivation_type
                }
                for d in self.derivations
            ],
            "associations": [
                {
                    "activity": a.activity_id,
                    "agent": a.agent_id,
                    "role": a.role
                }
                for a in self.associations
            ],
            "attributions": [
                {
                    "entity": a.entity_id,
                    "agent": a.agent_id
                }
                for a in self.attributions
            ]
        }

    def export_json(self, pretty: bool = True) -> str:
        """JSON形式でエクスポート"""
        if pretty:
            return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def export_turtle(self) -> str:
        """Turtle (RDF) 形式でエクスポート"""
        lines = [
            "@prefix prov: <http://www.w3.org/ns/prov#> .",
            "@prefix ex: <" + self.namespace + "> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            ""
        ]

        # Entities
        for entity in self.entities.values():
            lines.append(f"ex:{entity.id} a prov:Entity ;")
            lines.append(f"    prov:type \"{entity.type_name}\" ;")
            lines.append(f"    prov:value \"{self._escape_turtle(str(entity.value))}\" ;")
            lines.append(f"    prov:generatedAtTime \"{entity.timestamp}\"^^xsd:dateTime .")
            lines.append("")

        # Activities
        for activity in self.activities.values():
            lines.append(f"ex:{activity.id} a prov:Activity ;")
            lines.append(f"    ex:funcId \"{activity.func_id}\" ;")
            lines.append(f"    ex:funcSignature \"{self._escape_turtle(activity.func_signature)}\" ;")
            lines.append(f"    prov:startedAtTime \"{activity.start_time}\"^^xsd:dateTime")
            if activity.end_time:
                lines.append(f"    ; prov:endedAtTime \"{activity.end_time}\"^^xsd:dateTime")
            lines.append("    .")
            lines.append("")

        # Agents
        for agent in self.agents.values():
            lines.append(f"ex:{agent.id} a prov:Agent ;")
            lines.append(f"    prov:name \"{agent.name}\" ;")
            lines.append(f"    ex:agentType \"{agent.agent_type}\" .")
            lines.append("")

        # Usages
        for usage in self.usages:
            lines.append(f"ex:{usage.activity_id} prov:used ex:{usage.entity_id} ;")
            if usage.role:
                lines.append(f"    prov:hadRole \"{usage.role}\" ;")
            lines.append(f"    prov:atTime \"{usage.timestamp}\"^^xsd:dateTime .")
            lines.append("")

        # Generations
        for generation in self.generations:
            lines.append(f"ex:{generation.entity_id} prov:wasGeneratedBy ex:{generation.activity_id} ;")
            if generation.role:
                lines.append(f"    prov:hadRole \"{generation.role}\" ;")
            lines.append(f"    prov:atTime \"{generation.timestamp}\"^^xsd:dateTime .")
            lines.append("")

        # Derivations
        for derivation in self.derivations:
            lines.append(f"ex:{derivation.derived_entity_id} prov:wasDerivedFrom ex:{derivation.source_entity_id}")
            if derivation.activity_id:
                lines.append(f"    ; prov:qualifiedDerivation [")
                lines.append(f"        a prov:Derivation ;")
                lines.append(f"        prov:entity ex:{derivation.source_entity_id} ;")
                lines.append(f"        prov:hadActivity ex:{derivation.activity_id}")
                lines.append(f"    ]")
            lines.append("    .")
            lines.append("")

        # Associations
        for association in self.associations:
            lines.append(f"ex:{association.activity_id} prov:wasAssociatedWith ex:{association.agent_id}")
            if association.role:
                lines.append(f"    ; prov:hadRole \"{association.role}\"")
            lines.append("    .")
            lines.append("")

        # Attributions
        for attribution in self.attributions:
            lines.append(f"ex:{attribution.entity_id} prov:wasAttributedTo ex:{attribution.agent_id} .")
            lines.append("")

        return "\n".join(lines)

    def export_jsonld(self) -> str:
        """JSON-LD形式でエクスポート"""
        context = {
            "@context": {
                "prov": "http://www.w3.org/ns/prov#",
                "ex": self.namespace,
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "Entity": "prov:Entity",
                "Activity": "prov:Activity",
                "Agent": "prov:Agent",
                "used": {"@id": "prov:used", "@type": "@id"},
                "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
                "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
                "wasAssociatedWith": {"@id": "prov:wasAssociatedWith", "@type": "@id"},
                "wasAttributedTo": {"@id": "prov:wasAttributedTo", "@type": "@id"},
                "startedAtTime": {"@id": "prov:startedAtTime", "@type": "xsd:dateTime"},
                "endedAtTime": {"@id": "prov:endedAtTime", "@type": "xsd:dateTime"},
                "generatedAtTime": {"@id": "prov:generatedAtTime", "@type": "xsd:dateTime"}
            }
        }

        graph = []

        # Entities
        for entity in self.entities.values():
            node = {
                "@id": f"ex:{entity.id}",
                "@type": "Entity",
                "prov:type": entity.type_name,
                "prov:value": str(entity.value),
                "generatedAtTime": entity.timestamp
            }
            graph.append(node)

        # Activities
        for activity in self.activities.values():
            node = {
                "@id": f"ex:{activity.id}",
                "@type": "Activity",
                "ex:funcId": activity.func_id,
                "ex:funcSignature": activity.func_signature,
                "startedAtTime": activity.start_time
            }
            if activity.end_time:
                node["endedAtTime"] = activity.end_time
            graph.append(node)

        # Agents
        for agent in self.agents.values():
            node = {
                "@id": f"ex:{agent.id}",
                "@type": "Agent",
                "prov:name": agent.name,
                "ex:agentType": agent.agent_type
            }
            graph.append(node)

        # Usages
        for usage in self.usages:
            # アクティビティノードに追加
            for node in graph:
                if node.get("@id") == f"ex:{usage.activity_id}":
                    if "used" not in node:
                        node["used"] = []
                    node["used"].append(f"ex:{usage.entity_id}")

        # Generations
        for generation in self.generations:
            # エンティティノードに追加
            for node in graph:
                if node.get("@id") == f"ex:{generation.entity_id}":
                    node["wasGeneratedBy"] = f"ex:{generation.activity_id}"

        # Derivations
        for derivation in self.derivations:
            for node in graph:
                if node.get("@id") == f"ex:{derivation.derived_entity_id}":
                    if "wasDerivedFrom" not in node:
                        node["wasDerivedFrom"] = []
                    node["wasDerivedFrom"].append(f"ex:{derivation.source_entity_id}")

        # Associations
        for association in self.associations:
            for node in graph:
                if node.get("@id") == f"ex:{association.activity_id}":
                    if "wasAssociatedWith" not in node:
                        node["wasAssociatedWith"] = []
                    node["wasAssociatedWith"].append(f"ex:{association.agent_id}")

        # Attributions
        for attribution in self.attributions:
            for node in graph:
                if node.get("@id") == f"ex:{attribution.entity_id}":
                    if "wasAttributedTo" not in node:
                        node["wasAttributedTo"] = []
                    node["wasAttributedTo"].append(f"ex:{attribution.agent_id}")

        result = {**context, "@graph": graph}
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _escape_turtle(self, s: str) -> str:
        """Turtle用の文字列エスケープ"""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

    def get_entity_lineage(self, entity_id: str) -> List[str]:
        """エンティティの系譜（祖先のリスト）を取得"""
        lineage = []
        current = entity_id
        visited = set()

        while current and current not in visited:
            lineage.append(current)
            visited.add(current)

            # 派生元を探す
            source = None
            for derivation in self.derivations:
                if derivation.derived_entity_id == current:
                    source = derivation.source_entity_id
                    break

            current = source

        return lineage

    def get_activity_chain(self, entity_id: str) -> List[str]:
        """エンティティを生成したアクティビティのチェーンを取得"""
        chain = []
        lineage = self.get_entity_lineage(entity_id)

        for ent_id in lineage:
            for generation in self.generations:
                if generation.entity_id == ent_id:
                    chain.append(generation.activity_id)
                    break

        return chain


class ProvenanceTracker:
    """来歴追跡ヘルパー"""

    def __init__(self, graph: Optional[ProvenanceGraph] = None):
        self.graph = graph or ProvenanceGraph()
        self.enabled = True

    def track_function_execution(
        self,
        func_id: str,
        func_signature: str,
        input_entity_ids: List[str],
        output_value: Any,
        output_type: str
    ) -> str:
        """関数実行を追跡"""
        if not self.enabled:
            return None

        # アクティビティを作成
        activity_id = self.graph.add_activity(
            activity_id=None,
            func_id=func_id,
            func_signature=func_signature
        )

        # システムエージェントと関連付け
        self.graph.add_association(activity_id, self.graph.system_agent)

        # 入力の使用を記録
        for i, input_id in enumerate(input_entity_ids):
            self.graph.add_usage(activity_id, input_id, role=f"input_{i}")

        # 出力エンティティを作成
        output_id = self.graph.add_entity(
            entity_id=None,
            type_name=output_type,
            value=output_value
        )

        # 生成関係を記録
        self.graph.add_generation(output_id, activity_id, role="output")

        # 派生関係を記録
        for input_id in input_entity_ids:
            self.graph.add_derivation(output_id, input_id, activity_id)

        # アクティビティを終了
        self.graph.end_activity(activity_id)

        return output_id
