"""
型理論ベースオントロジー合成システム - コアライブラリ

型充足（Type Inhabitation）問題をベースに、オントロジー間の変換パスを自動探索・合成する。

改善版: 多引数関数の完全サポート
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union, Set
from enum import Enum
import heapq
from functools import reduce
import operator


@dataclass
class TypeDef:
    """型定義"""
    name: str
    attrs: Dict[str, str] = field(default_factory=dict)
    schema: Optional[Dict[str, Any]] = None  # 構造化データのスキーマ（JSON/XMLなど）

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, TypeDef):
            return self.name == other.name
        return False

    @property
    def is_structured(self) -> bool:
        """構造化データ型かどうか"""
        return self.schema is not None


@dataclass
class ProductType:
    """直積型（タプル型）"""
    name: str
    components: List[str]  # 構成する型名のリスト
    
    def __hash__(self):
        return hash(self.name)


@dataclass
class Func:
    """関数定義"""
    id: str                           # 関数名
    dom: Union[str, List[str]]        # ドメイン型（単一または複数）
    cod: str                          # コドメイン型
    cost: float = 1.0                 # コスト
    conf: float = 1.0                 # 信頼度
    impl: Dict[str, Any] = field(default_factory=dict)  # 実装仕様
    inverse_of: Optional[str] = None  # 逆関数
    doc: str = ""                     # ドキュメント
    
    @property
    def is_multiarg(self) -> bool:
        """多引数関数かどうか"""
        return isinstance(self.dom, list)
    
    @property
    def dom_types(self) -> List[str]:
        """ドメイン型のリスト"""
        if isinstance(self.dom, list):
            return self.dom
        return [self.dom]
    
    @property
    def arity(self) -> int:
        """引数の数"""
        return len(self.dom_types)
    
    @property
    def signature(self) -> str:
        """シグネチャ文字列"""
        if self.is_multiarg:
            dom_str = f"({', '.join(self.dom)})"
        else:
            dom_str = self.dom
        return f"{dom_str} -> {self.cod}"
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class UnitConversion:
    """単位変換ルール"""
    from_unit: str
    to_unit: str
    factor: float  # to = from * factor
    
    def convert(self, value: float) -> float:
        return value * self.factor


class UnitRegistry:
    """単位変換レジストリ"""
    
    def __init__(self):
        self.conversions: Dict[Tuple[str, str], UnitConversion] = {}
        self._init_default_conversions()
    
    def _init_default_conversions(self):
        """デフォルトの単位変換ルールを登録"""
        default_conversions = [
            # エネルギー
            ("J", "kWh", 1 / 3.6e6),
            ("kWh", "J", 3.6e6),
            ("MJ", "J", 1e6),
            ("J", "MJ", 1e-6),
            ("MJ", "kWh", 1 / 3.6),
            ("kWh", "MJ", 3.6),
            # 質量
            ("kg", "t", 1e-3),
            ("t", "kg", 1e3),
            ("g", "kg", 1e-3),
            ("kg", "g", 1e3),
            # 距離
            ("m", "km", 1e-3),
            ("km", "m", 1e3),
            # CO2
            ("kg-CO2", "t-CO2", 1e-3),
            ("t-CO2", "kg-CO2", 1e3),
        ]
        for from_unit, to_unit, factor in default_conversions:
            self.register(from_unit, to_unit, factor)
    
    def register(self, from_unit: str, to_unit: str, factor: float):
        """変換ルールを登録"""
        conv = UnitConversion(from_unit, to_unit, factor)
        self.conversions[(from_unit, to_unit)] = conv
    
    def can_convert(self, from_unit: str, to_unit: str) -> bool:
        """変換可能かどうか"""
        if from_unit == to_unit:
            return True
        return (from_unit, to_unit) in self.conversions
    
    def get_conversion(self, from_unit: str, to_unit: str) -> Optional[UnitConversion]:
        """変換ルールを取得"""
        if from_unit == to_unit:
            return UnitConversion(from_unit, to_unit, 1.0)
        return self.conversions.get((from_unit, to_unit))


class Catalog:
    """型と関数のカタログ"""
    
    def __init__(self):
        self.types: Dict[str, TypeDef] = {}
        self.product_types: Dict[str, ProductType] = {}
        self.funcs: List[Func] = []
        self.by_cod: Dict[str, List[Func]] = {}  # コドメインでインデックス
        self.by_dom: Dict[str, List[Func]] = {}  # ドメインでインデックス
        self.unit_registry: UnitRegistry = UnitRegistry()
    
    def add_type(self, type_def: TypeDef):
        """型を追加"""
        self.types[type_def.name] = type_def
    
    def add_product_type(self, product_type: ProductType):
        """Product型を追加"""
        self.product_types[product_type.name] = product_type
    
    def add_func(self, func: Func):
        """関数を追加"""
        self.funcs.append(func)
        
        # コドメインでインデックス
        if func.cod not in self.by_cod:
            self.by_cod[func.cod] = []
        self.by_cod[func.cod].append(func)
        
        # ドメインでインデックス（多引数の場合は各型について）
        for dom_type in func.dom_types:
            if dom_type not in self.by_dom:
                self.by_dom[dom_type] = []
            self.by_dom[dom_type].append(func)
    
    def funcs_returning(self, type_name: str) -> List[Func]:
        """指定された型を返す関数のリスト"""
        return self.by_cod.get(type_name, [])
    
    def funcs_accepting(self, type_name: str) -> List[Func]:
        """指定された型を受け取る関数のリスト"""
        return self.by_dom.get(type_name, [])
    
    def get_type(self, type_name: str) -> Optional[Union[TypeDef, ProductType]]:
        """型を取得"""
        if type_name in self.types:
            return self.types[type_name]
        if type_name in self.product_types:
            return self.product_types[type_name]
        return None
    
    def is_product_type(self, type_name: str) -> bool:
        """Product型かどうか"""
        return type_name in self.product_types
    
    def get_unit(self, type_name: str) -> Optional[str]:
        """型の単位を取得"""
        if type_name in self.types:
            return self.types[type_name].attrs.get("unit")
        return None


# =============================================================================
# Proof（証明項）のデータ構造
# =============================================================================

class ProofNodeType(Enum):
    """Proofノードの種類"""
    IDENTITY = "identity"           # 恒等関数
    FUNCTION = "function"           # 単一関数適用
    COMPOSITION = "composition"     # 関数合成 (g ∘ f)
    TUPLE = "tuple"                 # タプル構築 ⟨f, g, h⟩
    PROJECTION = "projection"       # 射影 π_i


@dataclass
class ProofNode:
    """Proof（証明項）ノード"""
    node_type: ProofNodeType
    func: Optional[Func] = None           # FUNCTION の場合
    children: List['ProofNode'] = None    # COMPOSITION, TUPLE の場合
    index: int = 0                        # PROJECTION の場合
    source_type: str = ""                 # ソース型
    target_type: str = ""                 # ターゲット型
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    def to_string(self, indent: int = 0) -> str:
        """文字列表現"""
        prefix = "  " * indent
        
        if self.node_type == ProofNodeType.IDENTITY:
            return f"{prefix}id[{self.source_type}]"
        
        elif self.node_type == ProofNodeType.FUNCTION:
            return f"{prefix}{self.func.id}"
        
        elif self.node_type == ProofNodeType.COMPOSITION:
            # 合成: f ∘ g (右から左に適用)
            parts = [child.to_string(0) for child in self.children]
            return f"{prefix}{' ∘ '.join(parts)}"
        
        elif self.node_type == ProofNodeType.TUPLE:
            # タプル: ⟨f, g, h⟩
            parts = [child.to_string(0) for child in self.children]
            return f"{prefix}⟨{', '.join(parts)}⟩"
        
        elif self.node_type == ProofNodeType.PROJECTION:
            return f"{prefix}π_{self.index}"
        
        return f"{prefix}???"
    
    def to_compact_string(self) -> str:
        """コンパクトな文字列表現"""
        if self.node_type == ProofNodeType.IDENTITY:
            return f"id"
        
        elif self.node_type == ProofNodeType.FUNCTION:
            return self.func.id
        
        elif self.node_type == ProofNodeType.COMPOSITION:
            parts = [child.to_compact_string() for child in self.children]
            return " ∘ ".join(parts)
        
        elif self.node_type == ProofNodeType.TUPLE:
            parts = [child.to_compact_string() for child in self.children]
            return f"⟨{', '.join(parts)}⟩"
        
        elif self.node_type == ProofNodeType.PROJECTION:
            return f"π_{self.index}"
        
        return "???"
    
    def to_tree_string(self, indent: int = 0) -> str:
        """ツリー形式の文字列表現"""
        prefix = "  " * indent
        lines = []
        
        if self.node_type == ProofNodeType.IDENTITY:
            lines.append(f"{prefix}IDENTITY[{self.source_type}]")
        
        elif self.node_type == ProofNodeType.FUNCTION:
            lines.append(f"{prefix}FUNC: {self.func.id} : {self.func.signature}")
        
        elif self.node_type == ProofNodeType.COMPOSITION:
            lines.append(f"{prefix}COMPOSE:")
            for child in self.children:
                lines.append(child.to_tree_string(indent + 1))
        
        elif self.node_type == ProofNodeType.TUPLE:
            lines.append(f"{prefix}TUPLE ⟨...⟩:")
            for i, child in enumerate(self.children):
                lines.append(f"{prefix}  [{i}]:")
                lines.append(child.to_tree_string(indent + 2))
        
        return "\n".join(lines)


def make_identity(type_name: str) -> ProofNode:
    """恒等関数のProofを作成"""
    return ProofNode(
        node_type=ProofNodeType.IDENTITY,
        source_type=type_name,
        target_type=type_name
    )


def make_func(func: Func) -> ProofNode:
    """関数適用のProofを作成"""
    return ProofNode(
        node_type=ProofNodeType.FUNCTION,
        func=func,
        source_type=func.dom if isinstance(func.dom, str) else str(func.dom),
        target_type=func.cod
    )


def make_composition(proofs: List[ProofNode]) -> ProofNode:
    """関数合成のProofを作成"""
    if len(proofs) == 0:
        raise ValueError("Empty composition")
    if len(proofs) == 1:
        return proofs[0]
    
    # フラット化: 既存のCOMPOSITIONを展開
    flat = []
    for p in proofs:
        if p.node_type == ProofNodeType.COMPOSITION:
            flat.extend(p.children)
        elif p.node_type != ProofNodeType.IDENTITY:
            flat.append(p)
    
    if len(flat) == 0:
        return make_identity(proofs[0].source_type)
    if len(flat) == 1:
        return flat[0]
    
    return ProofNode(
        node_type=ProofNodeType.COMPOSITION,
        children=flat,
        source_type=flat[0].source_type,
        target_type=flat[-1].target_type
    )


def make_tuple(proofs: List[ProofNode]) -> ProofNode:
    """タプル構築のProofを作成"""
    return ProofNode(
        node_type=ProofNodeType.TUPLE,
        children=proofs,
        source_type="(" + ", ".join(p.source_type for p in proofs) + ")",
        target_type="(" + ", ".join(p.target_type for p in proofs) + ")"
    )


# =============================================================================
# 合成結果
# =============================================================================

@dataclass
class SynthesisResult:
    """合成結果（単一パス）"""
    cost: float
    confidence: float
    path: List[Func]
    proof: ProofNode
    
    @property
    def proof_string(self) -> str:
        """proof文字列"""
        return self.proof.to_compact_string()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost": self.cost,
            "confidence_est": self.confidence,
            "steps": [
                {
                    "id": f.id,
                    "sig": f.signature,
                    "cost": f.cost,
                    "conf": f.conf
                }
                for f in self.path
            ],
            "proof": self.proof_string
        }


@dataclass
class DAGNode:
    """DAGのノード"""
    id: str
    node_type: str  # "source", "transform", "aggregate", "goal"
    type_name: str
    func: Optional[Func] = None
    inputs: List[str] = field(default_factory=list)  # 入力ノードID
    path: List[Func] = field(default_factory=list)   # このノードに至るパス
    value: Any = None  # 実行時の値


@dataclass
class SynthesisDAG:
    """合成結果のDAG表現（多引数関数対応）"""
    nodes: Dict[str, DAGNode]
    source_nodes: List[str]
    goal_node: str
    total_cost: float
    total_confidence: float
    proof: ProofNode
    
    @property
    def proof_string(self) -> str:
        return self.proof.to_compact_string()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {
                k: {
                    "id": v.id,
                    "type": v.node_type,
                    "type_name": v.type_name,
                    "func": v.func.id if v.func else None,
                    "func_sig": v.func.signature if v.func else None,
                    "inputs": v.inputs,
                    "path": [f.id for f in v.path]
                }
                for k, v in self.nodes.items()
            },
            "source_nodes": self.source_nodes,
            "goal_node": self.goal_node,
            "total_cost": self.total_cost,
            "total_confidence": self.total_confidence,
            "proof": self.proof_string,
            "proof_tree": self.proof.to_tree_string()
        }
    
    def topological_order(self) -> List[str]:
        """トポロジカルソート順でノードIDを返す"""
        visited = set()
        order = []
        
        def visit(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            node = self.nodes[node_id]
            for input_id in node.inputs:
                visit(input_id)
            order.append(node_id)
        
        visit(self.goal_node)
        return order


# =============================================================================
# 合成アルゴリズム
# =============================================================================

def synthesize_backward(
    catalog: Catalog,
    src_type: str,
    goal_type: str,
    max_cost: float = 100.0,
    max_results: int = 10
) -> List[SynthesisResult]:
    """
    逆方向探索アルゴリズム（単一ソース用）
    """
    # 優先度付きキュー: (累積コスト, カウンター, 現在の型, パス, 信頼度)
    # カウンターを追加してFuncの比較を回避
    counter = 0
    pq: List[Tuple[float, int, str, List[Func], float]] = [(0.0, counter, goal_type, [], 1.0)]
    visited_best: Dict[str, float] = {}
    results: List[SynthesisResult] = []
    
    while pq and len(results) < max_results:
        cum_cost, _, cur_type, path, confidence = heapq.heappop(pq)
        
        # ゴール到達
        if cur_type == src_type:
            # Proofを構築
            if path:
                proof_nodes = [make_func(f) for f in path]
                proof = make_composition(proof_nodes)
            else:
                proof = make_identity(src_type)
            
            results.append(SynthesisResult(
                cost=cum_cost,
                confidence=confidence,
                path=path,
                proof=proof
            ))
            continue
        
        # 枝刈り
        if cur_type in visited_best and cum_cost >= visited_best[cur_type]:
            continue
        visited_best[cur_type] = cum_cost
        
        # 展開
        for f in catalog.funcs_returning(cur_type):
            if f.is_multiarg:
                continue
            
            new_cost = cum_cost + f.cost
            if new_cost > max_cost:
                continue
            
            new_path = [f] + path
            new_confidence = confidence * f.conf
            next_type = f.dom
            
            counter += 1
            heapq.heappush(pq, (new_cost, counter, next_type, new_path, new_confidence))
    
    return sorted(results, key=lambda x: x.cost)


def synthesize_multiarg_full(
    catalog: Catalog,
    sources: Dict[str, str],  # {ソースID: 型名}
    goal_type: str,
    max_cost: float = 100.0,
    prefer_multiarg: bool = True  # 多引数関数を優先するか
) -> Optional[SynthesisDAG]:
    """
    多引数関数を完全サポートする合成アルゴリズム
    
    Args:
        catalog: カタログ
        sources: ソースの辞書 {ID: 型名}
        goal_type: ゴール型
        max_cost: 最大コスト
        prefer_multiarg: 多引数関数を優先するか（デフォルト: True）
    
    Returns:
        SynthesisDAG または None
    """
    multiarg_results: List[SynthesisDAG] = []
    product_results: List[SynthesisDAG] = []
    single_results: List[SynthesisDAG] = []
    
    # 1. 多引数関数を直接使う方法を試す
    for goal_func in catalog.funcs_returning(goal_type):
        if goal_func.is_multiarg:
            result = _try_synthesize_multiarg_func(
                catalog, sources, goal_type, goal_func, max_cost
            )
            if result:
                multiarg_results.append(result)
    
    # 2. Product型経由の方法を試す
    for product_name, product_type in catalog.product_types.items():
        result = _try_synthesize_via_product(
            catalog, sources, goal_type, product_name, product_type, max_cost
        )
        if result:
            product_results.append(result)
    
    # 3. 単一ソースからの単純パスも試す
    for src_id, src_type in sources.items():
        results = synthesize_backward(catalog, src_type, goal_type, max_cost)
        if results:
            result = _single_path_to_dag(src_id, src_type, goal_type, results[0])
            if result:
                single_results.append(result)
    
    # 優先順位に基づいて最適な結果を選択
    if prefer_multiarg:
        # 多引数関数を優先: 多引数 > Product型 > 単一パス
        all_results = (
            sorted(multiarg_results, key=lambda r: r.total_cost) +
            sorted(product_results, key=lambda r: r.total_cost) +
            sorted(single_results, key=lambda r: r.total_cost)
        )
    else:
        # コスト優先
        all_results = sorted(
            multiarg_results + product_results + single_results,
            key=lambda r: r.total_cost
        )
    
    return all_results[0] if all_results else None


def _try_synthesize_multiarg_func(
    catalog: Catalog,
    sources: Dict[str, str],
    goal_type: str,
    goal_func: Func,
    max_cost: float
) -> Optional[SynthesisDAG]:
    """多引数関数を使って合成を試みる"""
    required_types = goal_func.dom_types
    remaining_cost = max_cost - goal_func.cost
    
    # 各引数へのパスを探索
    arg_results: List[Tuple[str, SynthesisResult]] = []
    total_cost = goal_func.cost
    total_confidence = goal_func.conf
    used_sources: Set[str] = set()
    
    for required_type in required_types:
        found = False
        
        # まず直接一致するソースを探す
        for src_id, src_type in sources.items():
            if src_type == required_type and src_id not in used_sources:
                arg_results.append((src_id, SynthesisResult(
                    cost=0, confidence=1.0, path=[],
                    proof=make_identity(required_type)
                )))
                used_sources.add(src_id)
                found = True
                break
        
        if found:
            continue
        
        # パス探索
        for src_id, src_type in sources.items():
            results = synthesize_backward(
                catalog, src_type, required_type, remaining_cost - total_cost
            )
            if results:
                arg_results.append((src_id, results[0]))
                total_cost += results[0].cost
                total_confidence *= results[0].confidence
                found = True
                break
        
        if not found:
            return None
    
    # DAGを構築
    return _build_dag_from_multiarg(
        sources, goal_type, goal_func, arg_results, total_cost, total_confidence
    )


def _try_synthesize_via_product(
    catalog: Catalog,
    sources: Dict[str, str],
    goal_type: str,
    product_name: str,
    product_type: ProductType,
    max_cost: float
) -> Optional[SynthesisDAG]:
    """Product型経由で合成を試みる"""
    # Product型からゴールへのパス
    agg_results = synthesize_backward(catalog, product_name, goal_type, max_cost)
    if not agg_results:
        return None
    
    agg_result = agg_results[0]
    remaining_cost = max_cost - agg_result.cost
    
    # 各コンポーネントへのパスを探索
    component_results: List[Tuple[str, str, SynthesisResult]] = []  # (src_id, component, result)
    total_cost = agg_result.cost
    total_confidence = agg_result.confidence
    
    for component in product_type.components:
        found = False
        
        # 直接一致
        for src_id, src_type in sources.items():
            if src_type == component:
                component_results.append((src_id, component, SynthesisResult(
                    cost=0, confidence=1.0, path=[],
                    proof=make_identity(component)
                )))
                found = True
                break
        
        if found:
            continue
        
        # パス探索
        for src_id, src_type in sources.items():
            results = synthesize_backward(
                catalog, src_type, component, remaining_cost - total_cost
            )
            if results:
                component_results.append((src_id, component, results[0]))
                total_cost += results[0].cost
                total_confidence *= results[0].confidence
                found = True
                break
        
        if not found:
            return None
    
    # DAGを構築
    return _build_dag_from_product(
        sources, goal_type, product_name, product_type,
        component_results, agg_result, total_cost, total_confidence
    )


def _build_dag_from_multiarg(
    sources: Dict[str, str],
    goal_type: str,
    goal_func: Func,
    arg_results: List[Tuple[str, SynthesisResult]],
    total_cost: float,
    total_confidence: float
) -> SynthesisDAG:
    """多引数関数からDAGを構築"""
    nodes: Dict[str, DAGNode] = {}
    source_node_ids = []
    
    # ソースノード
    for src_id, src_type in sources.items():
        nodes[src_id] = DAGNode(
            id=src_id,
            node_type="source",
            type_name=src_type
        )
        source_node_ids.append(src_id)
    
    # 変換ノードと入力
    input_node_ids = []
    arg_proofs = []
    
    for i, (src_id, result) in enumerate(arg_results):
        required_type = goal_func.dom_types[i]
        
        if result.path:
            node_id = f"transform_{required_type}_{i}"
            nodes[node_id] = DAGNode(
                id=node_id,
                node_type="transform",
                type_name=required_type,
                func=result.path[-1] if result.path else None,
                inputs=[src_id],
                path=result.path
            )
            input_node_ids.append(node_id)
            arg_proofs.append(result.proof)
        else:
            input_node_ids.append(src_id)
            arg_proofs.append(make_identity(required_type))
    
    # ゴールノード
    goal_node_id = "goal"
    nodes[goal_node_id] = DAGNode(
        id=goal_node_id,
        node_type="goal",
        type_name=goal_type,
        func=goal_func,
        inputs=input_node_ids
    )
    
    # Proofを構築: ⟨path1, path2, path3⟩ ∘ aggregateFunc
    tuple_proof = make_tuple(arg_proofs)
    full_proof = make_composition([tuple_proof, make_func(goal_func)])
    
    return SynthesisDAG(
        nodes=nodes,
        source_nodes=source_node_ids,
        goal_node=goal_node_id,
        total_cost=total_cost,
        total_confidence=total_confidence,
        proof=full_proof
    )


def _build_dag_from_product(
    sources: Dict[str, str],
    goal_type: str,
    product_name: str,
    product_type: ProductType,
    component_results: List[Tuple[str, str, SynthesisResult]],
    agg_result: SynthesisResult,
    total_cost: float,
    total_confidence: float
) -> SynthesisDAG:
    """Product型経由のDAGを構築"""
    nodes: Dict[str, DAGNode] = {}
    source_node_ids = []
    
    # ソースノード
    for src_id, src_type in sources.items():
        nodes[src_id] = DAGNode(
            id=src_id,
            node_type="source",
            type_name=src_type
        )
        source_node_ids.append(src_id)
    
    # 各コンポーネントへの変換ノード
    component_node_ids = []
    component_proofs = []
    
    for i, (src_id, component, result) in enumerate(component_results):
        if result.path:
            node_id = f"transform_{component}_{i}"
            nodes[node_id] = DAGNode(
                id=node_id,
                node_type="transform",
                type_name=component,
                func=result.path[-1] if result.path else None,
                inputs=[src_id],
                path=result.path
            )
            component_node_ids.append(node_id)
            component_proofs.append(result.proof)
        else:
            component_node_ids.append(src_id)
            component_proofs.append(make_identity(component))
    
    # 集約ノード
    agg_node_id = "aggregate"
    agg_func = agg_result.path[0] if agg_result.path else None
    nodes[agg_node_id] = DAGNode(
        id=agg_node_id,
        node_type="aggregate",
        type_name=goal_type,
        func=agg_func,
        inputs=component_node_ids,
        path=agg_result.path
    )
    
    # Proofを構築: ⟨path1, path2, path3⟩ ∘ aggregateAllScopes
    tuple_proof = make_tuple(component_proofs)
    if agg_result.path:
        full_proof = make_composition([tuple_proof, agg_result.proof])
    else:
        full_proof = tuple_proof
    
    return SynthesisDAG(
        nodes=nodes,
        source_nodes=source_node_ids,
        goal_node=agg_node_id,
        total_cost=total_cost,
        total_confidence=total_confidence,
        proof=full_proof
    )


def _single_path_to_dag(
    src_id: str,
    src_type: str,
    goal_type: str,
    result: SynthesisResult
) -> SynthesisDAG:
    """単一パスをDAGに変換"""
    nodes: Dict[str, DAGNode] = {}
    
    # ソースノード
    nodes[src_id] = DAGNode(
        id=src_id,
        node_type="source",
        type_name=src_type
    )
    
    # ゴールノード
    nodes["goal"] = DAGNode(
        id="goal",
        node_type="goal",
        type_name=goal_type,
        func=result.path[-1] if result.path else None,
        inputs=[src_id],
        path=result.path
    )
    
    return SynthesisDAG(
        nodes=nodes,
        source_nodes=[src_id],
        goal_node="goal",
        total_cost=result.cost,
        total_confidence=result.confidence,
        proof=result.proof
    )


# =============================================================================
# 後方互換性のためのラッパー
# =============================================================================

def synthesize_multiarg(
    catalog: Catalog,
    sources: List[Tuple[str, Any]],
    goal_type: str,
    max_cost: float = 100.0
) -> Optional[SynthesisDAG]:
    """
    後方互換性のためのラッパー
    
    Args:
        sources: [(型名, 値), ...] のリスト
        
    Returns:
        SynthesisDAG
    """
    # ソースを辞書に変換
    sources_dict = {}
    for i, (type_name, _) in enumerate(sources):
        src_id = f"source_{type_name}_{i}"
        sources_dict[src_id] = type_name
    
    return synthesize_multiarg_full(catalog, sources_dict, goal_type, max_cost)


# =============================================================================
# ヘルパー関数
# =============================================================================

def compute_confidence(path: List[Func]) -> float:
    """パスの信頼度を計算"""
    if not path:
        return 1.0
    return reduce(operator.mul, (f.conf for f in path), 1.0)


def compute_cost(path: List[Func]) -> float:
    """パスのコストを計算"""
    return sum(f.cost for f in path)
