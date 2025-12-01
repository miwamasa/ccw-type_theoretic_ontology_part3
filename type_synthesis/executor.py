"""
実行エンジン

パス（関数のリスト）およびDAGを実際に実行し、データを変換する。

サポートする実装タイプ:
- sparql: SPARQLクエリ実行
- formula: 数式評価
- rest: REST API呼び出し
- builtin: 組み込み関数
- unit_conversion: 単位変換
"""

import re
import json
import math
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from synth_lib import (
    Func, Catalog, SynthesisResult, SynthesisDAG, DAGNode,
    synthesize_backward, synthesize_multiarg_full
)


@dataclass
class ExecutionContext:
    """実行コンテキスト"""
    # SPARQL用
    sparql_endpoint: Optional[str] = None
    sparql_prefixes: Dict[str, str] = None
    
    # REST用
    rest_headers: Dict[str, str] = None
    
    # 数式用の変数
    variables: Dict[str, Any] = None
    
    # 排出係数などの定数
    constants: Dict[str, float] = None
    
    def __post_init__(self):
        if self.sparql_prefixes is None:
            self.sparql_prefixes = {}
        if self.rest_headers is None:
            self.rest_headers = {}
        if self.variables is None:
            self.variables = {}
        if self.constants is None:
            self.constants = {
                "emission_factor": 2.5,  # kg-CO2 per kg fuel
                "efficiency": 0.35,       # エネルギー効率
                "kWh_to_CO2": 0.5,        # kg-CO2 per kWh
            }


class ExecutionError(Exception):
    """実行エラー"""
    pass


class Executor:
    """実行エンジン"""
    
    def __init__(self, context: ExecutionContext = None):
        self.context = context or ExecutionContext()
        self._builtins: Dict[str, Callable] = {
            "identity": lambda x: x,
            "sum": lambda x: sum(x) if isinstance(x, (list, tuple)) else x,
            "product": lambda x: math.prod(x) if isinstance(x, (list, tuple)) else x,
            "average": lambda x: sum(x) / len(x) if isinstance(x, (list, tuple)) and len(x) > 0 else x,
            "first": lambda x: x[0] if isinstance(x, (list, tuple)) else x,
            "last": lambda x: x[-1] if isinstance(x, (list, tuple)) else x,
            "count": lambda x: len(x) if isinstance(x, (list, tuple)) else 1,
            "abs": lambda x: abs(x),
            "round": lambda x: round(x),
        }
    
    def execute_path(
        self, 
        path: List[Func], 
        input_value: Any
    ) -> Any:
        """
        パス（関数のリスト）を実行
        
        Args:
            path: 関数のリスト
            input_value: 入力値
        
        Returns:
            変換結果
        """
        result = input_value
        
        for func in path:
            result = self.execute_func(func, result)
        
        return result
    
    def execute_dag(
        self,
        dag: SynthesisDAG,
        source_values: Dict[str, Any]
    ) -> Any:
        """
        DAGを実行
        
        Args:
            dag: 合成結果のDAG
            source_values: ソースノードID -> 値 のマッピング
        
        Returns:
            ゴールノードの値
        """
        # トポロジカル順で実行
        order = dag.topological_order()
        node_values: Dict[str, Any] = {}
        
        for node_id in order:
            node = dag.nodes[node_id]
            
            if node.node_type == "source":
                # ソースノード: 入力値を取得
                if node_id in source_values:
                    node_values[node_id] = source_values[node_id]
                else:
                    # 型名でも探す
                    found = False
                    for key, val in source_values.items():
                        if node.type_name in key or key in node.type_name:
                            node_values[node_id] = val
                            found = True
                            break
                    if not found:
                        # 最初の値を使用
                        node_values[node_id] = list(source_values.values())[0]
            
            elif node.node_type == "transform":
                # 変換ノード: パスを実行
                input_node_id = node.inputs[0]
                input_value = node_values[input_node_id]
                
                if node.path:
                    node_values[node_id] = self.execute_path(node.path, input_value)
                elif node.func:
                    node_values[node_id] = self.execute_func(node.func, input_value)
                else:
                    node_values[node_id] = input_value
            
            elif node.node_type in ("aggregate", "goal"):
                # 集約/ゴールノード
                if len(node.inputs) > 1:
                    # 複数入力: タプルを構築
                    input_values = tuple(node_values[inp_id] for inp_id in node.inputs)
                    
                    if node.path:
                        # パス全体を実行
                        node_values[node_id] = self.execute_path(node.path, input_values)
                    elif node.func:
                        node_values[node_id] = self.execute_func(node.func, input_values)
                    else:
                        node_values[node_id] = input_values
                else:
                    # 単一入力
                    input_value = node_values[node.inputs[0]] if node.inputs else None
                    
                    if node.path:
                        node_values[node_id] = self.execute_path(node.path, input_value)
                    elif node.func:
                        node_values[node_id] = self.execute_func(node.func, input_value)
                    else:
                        node_values[node_id] = input_value
        
        return node_values[dag.goal_node]
    
    def execute_func(self, func: Func, input_value: Any) -> Any:
        """
        単一の関数を実行
        
        Args:
            func: 関数
            input_value: 入力値
        
        Returns:
            出力値
        """
        impl = func.impl
        impl_type = impl.get("type", "identity")
        
        if impl_type == "sparql":
            return self._execute_sparql(impl, input_value)
        elif impl_type == "formula":
            return self._execute_formula(impl, input_value)
        elif impl_type == "rest":
            return self._execute_rest(impl, input_value)
        elif impl_type == "builtin":
            return self._execute_builtin(impl, input_value)
        elif impl_type == "unit_conversion":
            return self._execute_unit_conversion(impl, input_value)
        elif impl_type == "json":
            return self._execute_json(impl, input_value)
        elif impl_type == "template":
            return self._execute_template(impl, input_value)
        else:
            raise ExecutionError(f"Unknown impl type: {impl_type}")
    
    def _execute_sparql(self, impl: Dict, input_value: Any) -> Any:
        """SPARQLクエリを実行"""
        query = impl.get("query", "")
        
        # プレースホルダーを置換
        query = self._substitute_placeholders(query, input_value)
        
        if self.context.sparql_endpoint:
            # 実際のSPARQLエンドポイントに送信
            try:
                import requests
                
                # プレフィックスを追加
                prefixes = "\n".join(
                    f"PREFIX {k}: <{v}>" 
                    for k, v in self.context.sparql_prefixes.items()
                )
                full_query = f"{prefixes}\n{query}"
                
                response = requests.post(
                    self.context.sparql_endpoint,
                    data={"query": full_query},
                    headers={"Accept": "application/sparql-results+json"}
                )
                response.raise_for_status()
                
                results = response.json()
                bindings = results.get("results", {}).get("bindings", [])
                
                if bindings:
                    # 最初の結果の最初の値を返す
                    first = bindings[0]
                    for var_name, var_data in first.items():
                        value = var_data.get("value", "")
                        # 数値に変換可能なら変換
                        try:
                            return float(value)
                        except ValueError:
                            return value
                
                return None
                
            except Exception as e:
                raise ExecutionError(f"SPARQL execution failed: {e}")
        else:
            # モック実行（デモ用）
            return self._mock_sparql(query, input_value)
    
    def _mock_sparql(self, query: str, input_value: Any) -> Any:
        """SPARQLのモック実行（デモ用）"""
        # 入力値からダミー値を生成
        if isinstance(input_value, dict):
            if "energy" in input_value:
                return input_value["energy"]
            if "fuel" in input_value:
                return input_value["fuel"]
            if "elec" in input_value:
                return input_value["elec"]
            return 1000.0  # デフォルト
        return 1000.0
    
    def _execute_formula(self, impl: Dict, input_value: Any) -> Any:
        """数式を評価"""
        expr = impl.get("expr", "")
        
        # 入力値を変数としてセットアップ
        local_vars = dict(self.context.constants)
        local_vars.update(self.context.variables)
        
        # 入力値の処理
        if isinstance(input_value, tuple):
            # Product型（タプル）の場合
            # 例: (scope1, scope2, scope3)
            for i, val in enumerate(input_value):
                local_vars[f"arg{i}"] = val
                local_vars[f"x{i}"] = val
            
            # よく使う名前も設定
            if len(input_value) == 3:
                local_vars["scope1"] = input_value[0]
                local_vars["scope2"] = input_value[1]
                local_vars["scope3"] = input_value[2]
            if len(input_value) == 2:
                local_vars["a"] = input_value[0]
                local_vars["b"] = input_value[1]
        elif isinstance(input_value, dict):
            local_vars.update(input_value)
        else:
            local_vars["x"] = input_value
            local_vars["input"] = input_value
            local_vars["value"] = input_value
            
            # 式に含まれるすべての識別子に入力値をマップ
            import re
            identifiers = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr))
            reserved = {'and', 'or', 'not', 'if', 'else', 'for', 'in', 'True', 'False', 'None'}
            
            for name in identifiers:
                if name not in local_vars and name not in reserved:
                    local_vars[name] = input_value
        
        # 数式をPython式に変換
        python_expr = self._formula_to_python(expr)
        
        # 評価
        try:
            # 安全な組み込み関数
            safe_builtins = {
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "len": len, "pow": pow,
                "sqrt": math.sqrt, "log": math.log, "exp": math.exp,
                "sin": math.sin, "cos": math.cos, "tan": math.tan,
            }
            
            result = eval(python_expr, {"__builtins__": safe_builtins}, local_vars)
            return result
            
        except Exception as e:
            raise ExecutionError(f"Formula evaluation failed: {expr} -> {python_expr}, error: {e}")
    
    def _formula_to_python(self, expr: str) -> str:
        """数式をPython式に変換"""
        # 代入式の場合は右辺だけ取り出す
        # 例: "co2 = fuel * emission_factor" -> "fuel * emission_factor"
        if '=' in expr:
            parts = expr.split('=', 1)
            if len(parts) == 2:
                return parts[1].strip()
        
        return expr
    
    def _execute_rest(self, impl: Dict, input_value: Any) -> Any:
        """REST APIを呼び出し"""
        method = impl.get("method", "GET")
        url = impl.get("url", "")
        
        # プレースホルダーを置換
        url = self._substitute_placeholders(url, input_value)
        
        try:
            import requests
            
            headers = dict(self.context.rest_headers)
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, json=input_value, headers=headers)
            else:
                raise ExecutionError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # JSON応答の場合
            try:
                return response.json()
            except:
                return response.text
                
        except ImportError:
            # requestsがない場合はモック
            return self._mock_rest(url, input_value)
        except Exception as e:
            raise ExecutionError(f"REST call failed: {e}")
    
    def _mock_rest(self, url: str, input_value: Any) -> Any:
        """RESTのモック実行"""
        return {"result": input_value, "value": 800}
    
    def _execute_builtin(self, impl: Dict, input_value: Any) -> Any:
        """組み込み関数を実行"""
        name = impl.get("name", "identity")
        
        if name not in self._builtins:
            raise ExecutionError(f"Unknown builtin function: {name}")
        
        return self._builtins[name](input_value)
    
    def _execute_unit_conversion(self, impl: Dict, input_value: Any) -> Any:
        """単位変換を実行"""
        factor = impl.get("factor", 1.0)

        if isinstance(input_value, (int, float)):
            return input_value * factor
        elif isinstance(input_value, (list, tuple)):
            return type(input_value)(v * factor for v in input_value)
        else:
            return input_value

    def _execute_json(self, impl: Dict, input_value: Any) -> Any:
        """JSON構造を生成"""
        schema = impl.get("schema", {})

        # スキーマに基づいてJSONオブジェクトを構築
        result = self._build_json_from_schema(schema, input_value)
        return result

    def _build_json_from_schema(self, schema: Dict[str, Any], input_value: Any) -> Dict[str, Any]:
        """スキーマから実際のJSONを構築"""
        result = {}

        # 入力値を変数としてセットアップ
        local_vars = dict(self.context.constants)
        local_vars.update(self.context.variables)

        # 入力値の処理
        if isinstance(input_value, tuple):
            # Product型（タプル）の場合
            for i, val in enumerate(input_value):
                local_vars[f"arg{i}"] = val
                local_vars[f"x{i}"] = val
            if len(input_value) == 3:
                local_vars["scope1"] = input_value[0]
                local_vars["scope2"] = input_value[1]
                local_vars["scope3"] = input_value[2]
        elif isinstance(input_value, dict):
            local_vars.update(input_value)
        else:
            local_vars["value"] = input_value
            local_vars["input"] = input_value

        # スキーマの各フィールドを処理
        for key, value_spec in schema.items():
            if isinstance(value_spec, str):
                # 式の場合: 評価する
                try:
                    safe_builtins = {
                        "abs": abs, "round": round, "min": min, "max": max,
                        "sum": sum, "len": len, "str": str, "int": int, "float": float,
                        "isinstance": isinstance, "dict": dict, "list": list, "tuple": tuple,
                        "dir": dir,
                    }
                    result[key] = eval(value_spec, {"__builtins__": safe_builtins}, local_vars)
                except Exception as e:
                    # 評価できない場合はそのまま文字列として扱う
                    # デバッグ用: print(f"Failed to evaluate '{value_spec}': {e}")
                    result[key] = value_spec
            elif isinstance(value_spec, dict):
                # ネストされたオブジェクトの場合: 再帰的に処理
                result[key] = self._build_json_from_schema(value_spec, input_value)
            elif isinstance(value_spec, list):
                # リストの場合
                result[key] = [
                    self._build_json_from_schema(item, input_value) if isinstance(item, dict) else item
                    for item in value_spec
                ]
            else:
                # その他: そのまま設定
                result[key] = value_spec

        return result

    def _execute_template(self, impl: Dict, input_value: Any) -> Any:
        """テンプレートからXML/JSONを生成"""
        template_str = impl.get("template", "")
        mappings = impl.get("mappings", {})

        # 入力値を変数としてセットアップ
        local_vars = dict(self.context.constants)
        local_vars.update(self.context.variables)

        # 入力値の処理
        if isinstance(input_value, tuple):
            for i, val in enumerate(input_value):
                local_vars[f"arg{i}"] = val
            if len(input_value) == 3:
                local_vars["scope1"] = input_value[0]
                local_vars["scope2"] = input_value[1]
                local_vars["scope3"] = input_value[2]
        elif isinstance(input_value, dict):
            local_vars.update(input_value)
        else:
            local_vars["value"] = input_value

        # マッピングを評価
        evaluated_mappings = {}
        safe_builtins = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "len": len, "str": str, "int": int, "float": float,
        }

        for key, expr in mappings.items():
            try:
                evaluated_mappings[key] = eval(expr, {"__builtins__": safe_builtins}, local_vars)
            except:
                evaluated_mappings[key] = expr

        # テンプレート置換
        result = template_str
        for key, value in evaluated_mappings.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))

        return result

    def _substitute_placeholders(self, template: str, input_value: Any) -> str:
        """テンプレート内のプレースホルダーを置換"""
        result = template
        
        if isinstance(input_value, dict):
            for key, value in input_value.items():
                result = result.replace(f"{{{key}}}", str(value))
                result = result.replace(f"?{key}", str(value))
        else:
            result = result.replace("{id}", str(input_value))
            result = result.replace("{value}", str(input_value))
            result = result.replace("?input", str(input_value))
        
        return result
    
    def register_builtin(self, name: str, func: Callable):
        """組み込み関数を登録"""
        self._builtins[name] = func


# =============================================================================
# 高レベルAPI
# =============================================================================

def execute_synthesis_result(
    result: SynthesisResult,
    input_value: Any,
    context: ExecutionContext = None
) -> Any:
    """
    合成結果を実行
    
    Args:
        result: 合成結果
        input_value: 入力値
        context: 実行コンテキスト
    
    Returns:
        変換結果
    """
    executor = Executor(context)
    return executor.execute_path(result.path, input_value)


def execute_dag(
    dag: SynthesisDAG,
    source_values: Dict[str, Any],
    context: ExecutionContext = None
) -> Any:
    """
    DAGを実行
    
    Args:
        dag: 合成結果のDAG
        source_values: ソースノードID -> 値 のマッピング
        context: 実行コンテキスト
    
    Returns:
        変換結果
    """
    executor = Executor(context)
    return executor.execute_dag(dag, source_values)


def synthesize_and_execute(
    catalog: Catalog,
    sources: List[Tuple[str, Any]],
    goal: str,
    context: ExecutionContext = None,
    max_cost: float = 100.0
) -> Any:
    """
    合成と実行を一括で行う高レベルAPI
    
    Args:
        catalog: カタログ
        sources: [(型名, 値), ...] のリスト
        goal: ゴール型
        context: 実行コンテキスト
        max_cost: 最大コスト
    
    Returns:
        変換結果
    """
    executor = Executor(context)
    
    # 単一ソースの場合
    if len(sources) == 1:
        src_type, src_value = sources[0]
        results = synthesize_backward(catalog, src_type, goal, max_cost)
        
        if not results:
            raise ExecutionError(f"No path found from {src_type} to {goal}")
        
        return executor.execute_path(results[0].path, src_value)
    
    # 複数ソースの場合: DAGを使用
    sources_dict = {}
    source_values = {}
    
    for i, (type_name, value) in enumerate(sources):
        src_id = f"source_{type_name}_{i}"
        sources_dict[src_id] = type_name
        source_values[src_id] = value
    
    dag = synthesize_multiarg_full(catalog, sources_dict, goal, max_cost)
    
    if not dag:
        raise ExecutionError(f"No multi-source path found to {goal}")
    
    return executor.execute_dag(dag, source_values)


# =============================================================================
# 後方互換性
# =============================================================================

def execute_multisource_synthesis(
    result: SynthesisDAG,
    source_values: Dict[str, Any],
    context: ExecutionContext = None
) -> Any:
    """後方互換性のためのラッパー"""
    return execute_dag(result, source_values, context)


if __name__ == "__main__":
    # テスト
    from synth_lib import Func
    
    # テスト用の関数
    test_funcs = [
        Func(
            id="fuelToCO2",
            dom="Fuel",
            cod="CO2",
            impl={"type": "formula", "expr": "co2 = fuel * emission_factor"}
        ),
        Func(
            id="sumScopes",
            dom=["Scope1", "Scope2", "Scope3"],
            cod="Total",
            impl={"type": "formula", "expr": "total = scope1 + scope2 + scope3"}
        ),
    ]
    
    ctx = ExecutionContext(
        constants={"emission_factor": 2.5}
    )
    
    executor = Executor(ctx)
    
    # 単一入力テスト
    result = executor.execute_func(test_funcs[0], 100.0)
    print(f"fuelToCO2(100.0) = {result}")  # Expected: 250.0
    
    # 多引数テスト
    result = executor.execute_func(test_funcs[1], (100.0, 200.0, 300.0))
    print(f"sumScopes(100, 200, 300) = {result}")  # Expected: 600.0
