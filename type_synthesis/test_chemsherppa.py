#!/usr/bin/env python3
"""
ChemSHERPA 電池工場シナリオ テストケース

ABC電池株式会社のリチウムイオン電池製造における
化学物質管理フローをテスト。

シナリオ:
1. 調達フェーズ: 原材料（Li, Co, Pb, Cd）のデータ収集
2. 製造フェーズ: 電極材料加工、VOCロス計算
3. 輸送フェーズ: 包装材（PVC）データ統合
4. 最終出力: ChemSHERPAレポート生成
"""

import sys
import json
from typing import Dict, Any

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


# =============================================================================
# テストデータ（電池工場シナリオ）
# =============================================================================

# 調達フェーズのデータ
PROCUREMENT_DATA = {
    "material_name": "リチウム化合物",
    "weight": 100.0,        # 100kg
    "li_rate": 99.0,        # リチウム含有率 99%
    "pb_rate": 0.01,        # 鉛含有率 0.01%
    "co_rate": 60.0,        # コバルト含有率（コバルト酸化物として）
    "cd_rate": 0.005,       # カドミウム含有率 0.005%
}

# 製造フェーズのデータ
MANUFACTURING_DATA = {
    "input_weight": 150.0,  # 投入量 150kg（リチウム + コバルト酸化物）
    "loss_rate": 0.2,       # ロス率 20%
    "voc_amount": 5.0,      # VOC添加量 5kg
    "voc_loss_rate": 0.1,   # VOCロス率 10%（蒸発）
}

# 輸送フェーズのデータ
SHIPPING_DATA = {
    "product_count": 1000,  # 電池1000個
    "total_weight": 500.0,  # 総重量 500kg
    "packaging_weight": 10.0,  # 包装材重量 10kg
    "pvc_rate": 0.001,      # PVC含有率 0.001%
}


# =============================================================================
# テスト関数
# =============================================================================

def test_dsl_parse(catalog: Catalog) -> TestResult:
    """DSLパースのテスト"""
    type_count = len(catalog.types)
    product_count = len(catalog.product_types)
    func_count = len(catalog.funcs)
    multiarg_count = sum(1 for f in catalog.funcs if f.is_multiarg)
    
    message = (
        f"型: {type_count}, Product型: {product_count}, "
        f"関数: {func_count}, 多引数関数: {multiarg_count}"
    )
    
    # 期待値チェック
    if type_count >= 15 and func_count >= 10 and multiarg_count >= 1:
        return TestResult("DSLパース", True, message)
    else:
        return TestResult("DSLパース", False, f"不足: {message}")


def test_procurement_path(catalog: Catalog) -> TestResult:
    """調達フェーズ: RawMaterial -> ProcurementSubstanceData"""
    results = synthesize_backward(
        catalog, "RawMaterial", "ProcurementSubstanceData"
    )
    
    if not results:
        return TestResult("調達フェーズパス", False, "パスが見つかりません")
    
    best = results[0]
    return TestResult(
        "調達フェーズパス", True,
        f"proof: {best.proof_string}\n  コスト: {best.cost}, 信頼度: {best.confidence:.4f}"
    )


def test_manufacturing_path(catalog: Catalog) -> TestResult:
    """製造フェーズ: ManufacturingInput -> ManufacturingSubstanceData"""
    results = synthesize_backward(
        catalog, "ManufacturingInput", "ManufacturingSubstanceData"
    )
    
    if not results:
        return TestResult("製造フェーズパス", False, "パスが見つかりません")
    
    best = results[0]
    return TestResult(
        "製造フェーズパス", True,
        f"proof: {best.proof_string}\n  コスト: {best.cost}, 信頼度: {best.confidence:.4f}"
    )


def test_shipping_path(catalog: Catalog) -> TestResult:
    """輸送フェーズ: ShippingData -> ShippingSubstanceData"""
    results = synthesize_backward(
        catalog, "ShippingData", "ShippingSubstanceData"
    )
    
    if not results:
        return TestResult("輸送フェーズパス", False, "パスが見つかりません")
    
    best = results[0]
    return TestResult(
        "輸送フェーズパス", True,
        f"proof: {best.proof_string}\n  コスト: {best.cost}, 信頼度: {best.confidence:.4f}"
    )


def test_multiarg_integration(catalog: Catalog) -> TestResult:
    """多引数関数による3フェーズ統合テスト"""
    sources = {
        "raw_material": "RawMaterial",
        "mfg_input": "ManufacturingInput",
        "shipping": "ShippingData",
    }
    
    dag = synthesize_multiarg_full(
        catalog, sources, "ChemSHERPAReport"
    )
    
    if not dag:
        return TestResult("3フェーズ統合", False, "DAGが生成されませんでした")
    
    message = (
        f"proof: {dag.proof_string}\n"
        f"  総コスト: {dag.total_cost}\n"
        f"  総信頼度: {dag.total_confidence:.4f}\n"
        f"  ノード数: {len(dag.nodes)}"
    )
    
    return TestResult("3フェーズ統合", True, message)


def test_dag_execution(catalog: Catalog) -> TestResult:
    """DAG実行テスト（実データ使用）"""
    sources = {
        "raw_material": "RawMaterial",
        "mfg_input": "ManufacturingInput",
        "shipping": "ShippingData",
    }
    
    dag = synthesize_multiarg_full(
        catalog, sources, "ChemSHERPAReport"
    )
    
    if not dag:
        return TestResult("DAG実行", False, "DAGが生成されませんでした")
    
    # 実データを設定
    source_values = {
        "raw_material": PROCUREMENT_DATA,
        "mfg_input": MANUFACTURING_DATA,
        "shipping": SHIPPING_DATA,
    }
    
    context = ExecutionContext(
        constants={
            "pb_rate": PROCUREMENT_DATA["pb_rate"],
            "co_rate": PROCUREMENT_DATA["co_rate"],
            "cd_rate": PROCUREMENT_DATA["cd_rate"],
            "weight": PROCUREMENT_DATA["weight"],
            "loss_rate": MANUFACTURING_DATA["loss_rate"],
            "voc_loss_rate": MANUFACTURING_DATA["voc_loss_rate"],
            "pvc_rate": SHIPPING_DATA["pvc_rate"],
        }
    )
    
    try:
        result = execute_dag(dag, source_values, context)
        # dict型の結果を検証
        if isinstance(result, dict):
            has_header = "header" in result
            has_product = "product" in result
            has_substances = "substances" in result
            msg = f"実行成功 (dict型): header={has_header}, product={has_product}, substances={has_substances}"
            return TestResult("DAG実行", True, msg)
        else:
            return TestResult("DAG実行", True, f"実行結果: {result} (型: {type(result)})")
    except Exception as e:
        return TestResult("DAG実行", False, f"実行エラー: {e}")


def test_proof_structure(catalog: Catalog) -> TestResult:
    """Proof構造の詳細テスト"""
    sources = {
        "raw_material": "RawMaterial",
        "mfg_input": "ManufacturingInput",
        "shipping": "ShippingData",
    }
    
    dag = synthesize_multiarg_full(
        catalog, sources, "ChemSHERPAReport"
    )
    
    if not dag:
        return TestResult("Proof構造", False, "DAGが生成されませんでした")
    
    proof_tree = dag.proof.to_tree_string()
    
    message = (
        f"Proof (コンパクト):\n  {dag.proof_string}\n\n"
        f"Proof (ツリー):\n{proof_tree}"
    )
    
    return TestResult("Proof構造", True, message)


def test_compliance_calculation() -> TestResult:
    """規制遵守計算のテスト"""
    # 鉛含有量計算: 100kg × 0.01% = 0.01kg
    pb_amount = PROCUREMENT_DATA["weight"] * PROCUREMENT_DATA["pb_rate"] / 100
    
    # 電極材料重量: 150kg × (1 - 0.2) = 120kg
    electrode_weight = MANUFACTURING_DATA["input_weight"] * (1 - MANUFACTURING_DATA["loss_rate"])
    
    # 鉛濃度: 0.01kg / 120kg × 100 = 0.0083%
    pb_concentration = pb_amount / electrode_weight * 100
    
    # RoHS閾値チェック（0.1%未満で準拠）
    rohs_compliant = pb_concentration < 0.1
    
    message = (
        f"鉛含有量: {pb_amount:.4f} kg\n"
        f"  電極材料重量: {electrode_weight:.1f} kg\n"
        f"  鉛濃度: {pb_concentration:.4f} %\n"
        f"  RoHS準拠: {rohs_compliant} (閾値 0.1%)"
    )
    
    if rohs_compliant and abs(pb_concentration - 0.0083) < 0.001:
        return TestResult("規制遵守計算", True, message)
    else:
        return TestResult("規制遵守計算", False, message)


def test_synthesize_and_execute_api(catalog: Catalog) -> TestResult:
    """高レベルAPI: synthesize_and_execute のテスト"""
    sources = [
        ("RawMaterial", PROCUREMENT_DATA),
        ("ManufacturingInput", MANUFACTURING_DATA),
        ("ShippingData", SHIPPING_DATA),
    ]
    
    context = ExecutionContext(
        constants={
            "pb_rate": PROCUREMENT_DATA["pb_rate"],
            "weight": PROCUREMENT_DATA["weight"],
            "loss_rate": MANUFACTURING_DATA["loss_rate"],
            "voc_loss_rate": MANUFACTURING_DATA["voc_loss_rate"],
        }
    )
    
    try:
        result = synthesize_and_execute(
            catalog,
            sources,
            "ChemSHERPAReport",
            context
        )
        return TestResult("synthesize_and_execute API", True, f"結果: {result}")
    except Exception as e:
        return TestResult("synthesize_and_execute API", False, f"エラー: {e}")


# =============================================================================
# テスト実行
# =============================================================================

def run_tests():
    """全テストを実行"""
    print("=" * 80)
    print("ChemSHERPA 電池工場シナリオ テスト")
    print("=" * 80)
    
    print("\n【シナリオ概要】")
    print("  企業: ABC電池株式会社")
    print("  製品: スマートフォン用リチウムイオン電池")
    print("  目標: ChemSHERPA-CI/AI形式レポート生成")
    
    print("\n【テストデータ】")
    print(f"  調達: {PROCUREMENT_DATA}")
    print(f"  製造: {MANUFACTURING_DATA}")
    print(f"  輸送: {SHIPPING_DATA}")
    
    # DSLファイルをパース
    print("\n" + "-" * 80)
    print("DSLファイルをパース中...")
    catalog = parse_dsl_file("chemsherppa_battery.dsl")
    
    # 多引数関数を確認
    multiarg_funcs = [f for f in catalog.funcs if f.is_multiarg]
    print(f"  多引数関数: {len(multiarg_funcs)}")
    for f in multiarg_funcs:
        print(f"    - {f.id}: {f.signature}")
    
    # テストを実行
    tests = [
        lambda c: test_dsl_parse(c),
        lambda c: test_procurement_path(c),
        lambda c: test_manufacturing_path(c),
        lambda c: test_shipping_path(c),
        lambda c: test_multiarg_integration(c),
        lambda c: test_proof_structure(c),
        lambda _: test_compliance_calculation(),
        lambda c: test_dag_execution(c),
        lambda c: test_synthesize_and_execute_api(c),
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


def demo_chemsherppa_synthesis():
    """ChemSHERPA合成のデモンストレーション"""
    print("\n" + "=" * 80)
    print("ChemSHERPA レポート生成 デモ")
    print("=" * 80)
    
    catalog = parse_dsl_file("chemsherppa_battery.dsl")
    
    # ソースを定義
    sources = {
        "procurement": "RawMaterial",
        "manufacturing": "ManufacturingInput",
        "shipping": "ShippingData",
    }
    
    print("\n【入力ソース】")
    for src_id, src_type in sources.items():
        print(f"  {src_id}: {src_type}")
    print("  ゴール: ChemSHERPAReport")
    
    # 合成
    print("\n【合成結果】")
    dag = synthesize_multiarg_full(catalog, sources, "ChemSHERPAReport")
    
    if dag:
        print(f"  proof: {dag.proof_string}")
        print(f"  総コスト: {dag.total_cost}")
        print(f"  総信頼度: {dag.total_confidence:.4f}")
        
        print("\n【DAG構造（トポロジカル順）】")
        for node_id in dag.topological_order():
            node = dag.nodes[node_id]
            inputs_str = f" <- {node.inputs}" if node.inputs else ""
            func_str = f" [{node.func.id}]" if node.func else ""
            path_str = f" path={[f.id for f in node.path]}" if node.path else ""
            print(f"  {node_id}: {node.type_name}{func_str}{path_str}{inputs_str}")
        
        print("\n【Proof ツリー】")
        print(dag.proof.to_tree_string())
        
        # 実行
        print("\n【実行】")
        source_values = {
            "procurement": PROCUREMENT_DATA,
            "manufacturing": MANUFACTURING_DATA,
            "shipping": SHIPPING_DATA,
        }
        
        context = ExecutionContext()
        result = execute_dag(dag, source_values, context)

        print(f"  結果型: {type(result)}")

        # 実際に生成されたChemSHERPA JSON構造を表示
        print("\n【生成されたChemSHERPA JSONレポート】")
        if isinstance(result, dict):
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False))

            # 検証
            print("\n【JSONレポート検証】")
            if "header" in result:
                print(f"  ✓ ヘッダー: {result['header']['companyName']}")
            if "product" in result:
                print(f"  ✓ 製品: {result['product']['productName']}, 重量: {result['product'].get('mass', 'N/A')} {result['product'].get('unit', '')}")
            if "substances" in result:
                print(f"  ✓ 物質データ:")
                subs = result["substances"]
                if "lead" in subs:
                    pb = subs["lead"]
                    print(f"    - 鉛(Pb): {pb.get('amount', 'N/A')} kg, 濃度: {pb.get('concentration', 'N/A')}%, RoHS準拠: {pb.get('rohs_compliant', 'N/A')}")
                if "cobalt" in subs:
                    co = subs["cobalt"]
                    print(f"    - コバルト(Co): {co.get('amount', 'N/A')} kg, 濃度: {co.get('concentration', 'N/A')}%")
                if "pvc" in subs:
                    pvc = subs["pvc"]
                    print(f"    - PVC: {pvc.get('amount', 'N/A')} kg, 濃度: {pvc.get('concentration', 'N/A')}%")
            if "compliance" in result:
                print(f"  ✓ 総合遵守状況: RoHS={result['compliance'].get('rohs', 'N/A')}, REACH={result['compliance'].get('reach', 'N/A')}")
        else:
            print(f"  警告: 結果がdict型ではありません: {result}")
    else:
        print("  合成に失敗しました")


if __name__ == "__main__":
    ret = run_tests()
    
    if ret == 0:
        demo_chemsherppa_synthesis()
    
    sys.exit(ret)
