#!/usr/bin/env python3
"""
多引数関数の完全サポートテスト

GHG Scope 1, 2, 3 の集約を、多引数関数とDAGで完全に自動化。
"""

import sys
import json
from typing import Tuple

from dsl_parser import parse_dsl_file
from synth_lib import (
    synthesize_backward, 
    synthesize_multiarg_full,
    Catalog,
    SynthesisResult,
    SynthesisDAG
)
from executor import (
    ExecutionContext, 
    execute_synthesis_result,
    execute_dag,
    synthesize_and_execute,
    Executor
)


class TestResult:
    """テスト結果"""
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message


def test_scope1_path(catalog: Catalog) -> TestResult:
    """Scope1へのパスをテスト"""
    results = synthesize_backward(catalog, "Facility", "Scope1Emissions")
    
    if not results:
        return TestResult("Scope1パス探索", False, "パスが見つかりません")
    
    expected_funcs = {"facilityFuelConsumption", "fuelToScope1"}
    actual_funcs = {f.id for f in results[0].path}
    
    if expected_funcs == actual_funcs:
        return TestResult("Scope1パス探索", True, 
                         f"proof: {results[0].proof_string}")
    else:
        return TestResult("Scope1パス探索", False, 
                         f"期待: {expected_funcs}, 実際: {actual_funcs}")


def test_scope2_path(catalog: Catalog) -> TestResult:
    """Scope2へのパスをテスト"""
    results = synthesize_backward(catalog, "Facility", "Scope2Emissions")
    
    if not results:
        return TestResult("Scope2パス探索", False, "パスが見つかりません")
    
    expected_funcs = {"facilityElectricity", "electricityToScope2"}
    actual_funcs = {f.id for f in results[0].path}
    
    if expected_funcs == actual_funcs:
        return TestResult("Scope2パス探索", True,
                         f"proof: {results[0].proof_string}")
    else:
        return TestResult("Scope2パス探索", False,
                         f"期待: {expected_funcs}, 実際: {actual_funcs}")


def test_scope3_path(catalog: Catalog) -> TestResult:
    """Scope3へのパスをテスト"""
    results = synthesize_backward(catalog, "Organization", "Scope3Emissions")
    
    if not results:
        return TestResult("Scope3パス探索", False, "パスが見つかりません")
    
    actual_funcs = {f.id for f in results[0].path}
    return TestResult("Scope3パス探索", True,
                     f"proof: {results[0].proof_string}")


def test_multiarg_synthesis(catalog: Catalog) -> TestResult:
    """多引数関数による完全な合成テスト"""
    sources = {
        "facility1": "Facility",
        "facility2": "Facility",
        "org1": "Organization",
    }
    
    dag = synthesize_multiarg_full(catalog, sources, "TotalGHGEmissions")
    
    if not dag:
        return TestResult("多引数合成", False, "DAGが生成されませんでした")
    
    # DAGの構造を確認
    message = (
        f"proof: {dag.proof_string}\n"
        f"  コスト: {dag.total_cost}\n"
        f"  信頼度: {dag.total_confidence:.4f}\n"
        f"  ノード数: {len(dag.nodes)}"
    )
    
    return TestResult("多引数合成", True, message)


def test_dag_execution(catalog: Catalog) -> TestResult:
    """DAG実行テスト"""
    sources = {
        "facility1": "Facility",
        "facility2": "Facility",
        "org1": "Organization",
    }
    
    dag = synthesize_multiarg_full(catalog, sources, "TotalGHGEmissions")
    
    if not dag:
        return TestResult("DAG実行", False, "DAGが生成されませんでした")
    
    # 入力データ
    source_values = {
        "facility1": {"fuel": 400},     # Scope1用: 400 * 2.5 = 1000
        "facility2": {"elec": 3000},    # Scope2用: 3000 * 0.5 = 1500
        "org1": {"value": 800},         # Scope3用
    }
    
    context = ExecutionContext()
    
    try:
        result = execute_dag(dag, source_values, context)
        
        message = (
            f"実行結果: {result}\n"
            f"  proof: {dag.proof_string}"
        )
        
        return TestResult("DAG実行", True, message)
    except Exception as e:
        return TestResult("DAG実行", False, f"実行エラー: {e}")


def test_synthesize_and_execute(catalog: Catalog) -> TestResult:
    """高レベルAPI: synthesize_and_execute のテスト"""
    sources = [
        ("Facility", {"fuel": 400}),
        ("Facility", {"elec": 3000}),
        ("Organization", {"value": 800}),
    ]
    
    context = ExecutionContext()
    
    try:
        result = synthesize_and_execute(
            catalog,
            sources,
            "TotalGHGEmissions",
            context
        )
        
        return TestResult("synthesize_and_execute", True, f"結果: {result}")
    except Exception as e:
        return TestResult("synthesize_and_execute", False, f"エラー: {e}")


def test_proof_structure(catalog: Catalog) -> TestResult:
    """Proof構造の詳細テスト"""
    sources = {
        "facility1": "Facility",
        "facility2": "Facility",
        "org1": "Organization",
    }
    
    dag = synthesize_multiarg_full(catalog, sources, "TotalGHGEmissions")
    
    if not dag:
        return TestResult("Proof構造", False, "DAGが生成されませんでした")
    
    # Proof構造を出力
    proof_tree = dag.proof.to_tree_string()
    
    message = (
        f"Proof (コンパクト): {dag.proof_string}\n"
        f"Proof (ツリー):\n{proof_tree}"
    )
    
    return TestResult("Proof構造", True, message)


def test_dag_json_output(catalog: Catalog) -> TestResult:
    """DAGのJSON出力テスト"""
    sources = {
        "facility1": "Facility",
        "facility2": "Facility",
        "org1": "Organization",
    }
    
    dag = synthesize_multiarg_full(catalog, sources, "TotalGHGEmissions")
    
    if not dag:
        return TestResult("DAG JSON出力", False, "DAGが生成されませんでした")
    
    dag_dict = dag.to_dict()
    json_str = json.dumps(dag_dict, indent=2, ensure_ascii=False)
    
    return TestResult("DAG JSON出力", True, f"JSON出力:\n{json_str[:500]}...")


def run_tests():
    """全テストを実行"""
    print("=" * 80)
    print("多引数関数 完全サポートテスト")
    print("=" * 80)
    
    # DSLファイルをパース
    print("\nDSLファイルをパース中...")
    catalog = parse_dsl_file("ghg_scope123_product.dsl")
    print(f"  型: {len(catalog.types)}")
    print(f"  Product型: {len(catalog.product_types)}")
    print(f"  関数: {len(catalog.funcs)}")
    
    # 多引数関数を確認
    multiarg_funcs = [f for f in catalog.funcs if f.is_multiarg]
    print(f"  多引数関数: {len(multiarg_funcs)}")
    for f in multiarg_funcs:
        print(f"    - {f.id}: {f.signature}")
    
    # テストを実行
    tests = [
        test_scope1_path,
        test_scope2_path,
        test_scope3_path,
        test_multiarg_synthesis,
        test_proof_structure,
        test_dag_execution,
        test_synthesize_and_execute,
        test_dag_json_output,
    ]
    
    results = []
    print("\n" + "-" * 80)
    print("テスト実行")
    print("-" * 80)
    
    for test_func in tests:
        result = test_func(catalog)
        results.append(result)
        
        status = "✓" if result.passed else "✗"
        print(f"\n{status} {result.name}")
        if result.message:
            for line in result.message.split('\n'):
                print(f"  {line}")
    
    # サマリー
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print("\n" + "=" * 80)
    print("テスト結果サマリー")
    print("=" * 80)
    print(f"{'✓' if passed == total else '✗'} {passed}/{total} テストが成功")
    
    if passed == total:
        print("\n🎉 すべてのテストが成功しました！")
        return 0
    else:
        print("\n⚠️  一部のテストが失敗しました")
        return 1


def demo_full_ghg_synthesis():
    """GHG合成のデモンストレーション"""
    print("\n" + "=" * 80)
    print("GHG Scope 1,2,3 完全合成デモ")
    print("=" * 80)
    
    catalog = parse_dsl_file("ghg_scope123_product.dsl")
    
    # ソースを定義
    sources = {
        "facility_scope1": "Facility",
        "facility_scope2": "Facility", 
        "organization_scope3": "Organization",
    }
    
    print("\n【入力】")
    print("  ソース:")
    for src_id, src_type in sources.items():
        print(f"    {src_id}: {src_type}")
    print("  ゴール: TotalGHGEmissions")
    
    # 合成
    print("\n【合成結果】")
    dag = synthesize_multiarg_full(catalog, sources, "TotalGHGEmissions")
    
    if dag:
        print(f"  proof: {dag.proof_string}")
        print(f"  総コスト: {dag.total_cost}")
        print(f"  総信頼度: {dag.total_confidence:.4f}")
        
        print("\n【DAG構造】")
        for node_id in dag.topological_order():
            node = dag.nodes[node_id]
            inputs_str = f" <- {node.inputs}" if node.inputs else ""
            func_str = f" [{node.func.id}]" if node.func else ""
            print(f"  {node_id}: {node.type_name}{func_str}{inputs_str}")
        
        print("\n【Proof ツリー】")
        print(dag.proof.to_tree_string())
        
        # 実行
        print("\n【実行】")
        source_values = {
            "facility_scope1": {"fuel": 400},
            "facility_scope2": {"elec": 3000},
            "organization_scope3": {"value": 800},
        }
        
        print("  入力値:")
        for src_id, value in source_values.items():
            print(f"    {src_id}: {value}")
        
        context = ExecutionContext()
        result = execute_dag(dag, source_values, context)
        
        print(f"\n  結果: {result} kg-CO2")
    else:
        print("  合成に失敗しました")


if __name__ == "__main__":
    ret = run_tests()
    
    if ret == 0:
        demo_full_ghg_synthesis()
    
    sys.exit(ret)
