#!/usr/bin/env python3
"""
DSL統合テスト

パーサー、型合成、実行エンジンの統合テストを実行。
"""

import sys
import unittest
from typing import List, Dict, Any

from dsl_parser import parse_dsl, parse_dsl_file, DSLParseError
from synth_lib import (
    Catalog, TypeDef, ProductType, Func,
    synthesize_backward, synthesize_multiarg_full,
    SynthesisResult, SynthesisDAG
)
from executor import (
    ExecutionContext, Executor,
    execute_synthesis_result, synthesize_and_execute
)


class TestDSLParser(unittest.TestCase):
    """DSLパーサーのテスト"""
    
    def test_type_definition(self):
        """型定義のパース"""
        dsl = '''
type Product
type Energy [unit=J, range=>=0]
'''
        catalog = parse_dsl(dsl)
        
        self.assertIn("Product", catalog.types)
        self.assertIn("Energy", catalog.types)
        self.assertEqual(catalog.types["Energy"].attrs.get("unit"), "J")
    
    def test_product_type(self):
        """Product型のパース"""
        dsl = '''
type A
type B
type C
type ABC = A x B x C
'''
        catalog = parse_dsl(dsl)
        
        self.assertIn("ABC", catalog.product_types)
        self.assertEqual(catalog.product_types["ABC"].components, ["A", "B", "C"])
    
    def test_function_definition(self):
        """関数定義のパース"""
        dsl = '''
type A
type B

fn transform {
  sig: A -> B
  impl: formula("y = x * 2")
  cost: 1.5
  confidence: 0.95
  doc: "Transform A to B"
}
'''
        catalog = parse_dsl(dsl)
        
        self.assertEqual(len(catalog.funcs), 1)
        func = catalog.funcs[0]
        self.assertEqual(func.id, "transform")
        self.assertEqual(func.dom, "A")
        self.assertEqual(func.cod, "B")
        self.assertEqual(func.cost, 1.5)
        self.assertEqual(func.conf, 0.95)
    
    def test_multiarg_function(self):
        """多引数関数のパース"""
        dsl = '''
type A
type B
type C
type D

fn combine {
  sig: (A, B, C) -> D
  impl: formula("d = a + b + c")
  cost: 2
}
'''
        catalog = parse_dsl(dsl)
        
        func = catalog.funcs[0]
        self.assertTrue(func.is_multiarg)
        self.assertEqual(func.dom_types, ["A", "B", "C"])
        self.assertEqual(func.cod, "D")
    
    def test_parse_error(self):
        """パースエラーの検出"""
        dsl = '''
unknown_keyword Something
'''
        with self.assertRaises(DSLParseError):
            parse_dsl(dsl)


class TestSynthesisBackward(unittest.TestCase):
    """逆方向探索のテスト"""
    
    def setUp(self):
        """テスト用カタログを作成"""
        self.catalog = Catalog()
        
        # 型を追加
        for name in ["A", "B", "C", "D", "E"]:
            self.catalog.add_type(TypeDef(name=name))
        
        # 関数を追加 (A -> B -> C -> D)
        self.catalog.add_func(Func(id="f1", dom="A", cod="B", cost=1, conf=0.9))
        self.catalog.add_func(Func(id="f2", dom="B", cod="C", cost=2, conf=0.8))
        self.catalog.add_func(Func(id="f3", dom="C", cod="D", cost=1, conf=0.95))
        
        # 代替パス (A -> E -> D)
        self.catalog.add_func(Func(id="f4", dom="A", cod="E", cost=1, conf=0.7))
        self.catalog.add_func(Func(id="f5", dom="E", cod="D", cost=2, conf=0.85))
    
    def test_direct_path(self):
        """直接パスの探索"""
        results = synthesize_backward(self.catalog, "A", "B")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].cost, 1)
        self.assertEqual(len(results[0].path), 1)
        self.assertEqual(results[0].path[0].id, "f1")
    
    def test_chain_path(self):
        """チェーンパスの探索"""
        results = synthesize_backward(self.catalog, "A", "D")
        
        self.assertGreaterEqual(len(results), 1)
        
        # 最短パス (A -> E -> D) or (A -> B -> C -> D)
        best = results[0]
        self.assertGreaterEqual(best.cost, 3)
    
    def test_no_path(self):
        """パスが存在しない場合"""
        results = synthesize_backward(self.catalog, "D", "A")
        
        self.assertEqual(len(results), 0)
    
    def test_confidence_calculation(self):
        """信頼度の計算"""
        results = synthesize_backward(self.catalog, "A", "B")
        
        self.assertAlmostEqual(results[0].confidence, 0.9)
        
        results = synthesize_backward(self.catalog, "A", "C")
        # f1 (0.9) * f2 (0.8) = 0.72
        self.assertAlmostEqual(results[0].confidence, 0.72)


class TestExecutor(unittest.TestCase):
    """実行エンジンのテスト"""
    
    def setUp(self):
        self.context = ExecutionContext(
            constants={
                "emission_factor": 2.5,
                "efficiency": 0.35,
            }
        )
        self.executor = Executor(self.context)
    
    def test_formula_execution(self):
        """数式の実行"""
        func = Func(
            id="test",
            dom="A",
            cod="B",
            impl={"type": "formula", "expr": "y = x * 2"}
        )
        
        result = self.executor.execute_func(func, 10)
        self.assertEqual(result, 20)
    
    def test_formula_with_constants(self):
        """定数を使った数式"""
        func = Func(
            id="test",
            dom="Fuel",
            cod="CO2",
            impl={"type": "formula", "expr": "co2 = fuel * emission_factor"}
        )
        
        result = self.executor.execute_func(func, 100)
        self.assertEqual(result, 250)  # 100 * 2.5
    
    def test_tuple_formula(self):
        """タプル入力の数式"""
        func = Func(
            id="sum3",
            dom=["A", "B", "C"],
            cod="D",
            impl={"type": "formula", "expr": "total = scope1 + scope2 + scope3"}
        )
        
        result = self.executor.execute_func(func, (100, 200, 300))
        self.assertEqual(result, 600)
    
    def test_builtin_identity(self):
        """identity組み込み関数"""
        func = Func(
            id="test",
            dom="A",
            cod="A",
            impl={"type": "builtin", "name": "identity"}
        )
        
        result = self.executor.execute_func(func, 42)
        self.assertEqual(result, 42)
    
    def test_builtin_sum(self):
        """sum組み込み関数"""
        func = Func(
            id="test",
            dom="List",
            cod="Number",
            impl={"type": "builtin", "name": "sum"}
        )
        
        result = self.executor.execute_func(func, [1, 2, 3, 4, 5])
        self.assertEqual(result, 15)
    
    def test_path_execution(self):
        """パス全体の実行"""
        path = [
            Func(id="f1", dom="A", cod="B", 
                 impl={"type": "formula", "expr": "y = x * 2"}),
            Func(id="f2", dom="B", cod="C", 
                 impl={"type": "formula", "expr": "y = x + 10"}),
        ]
        
        result = self.executor.execute_path(path, 5)
        # 5 * 2 = 10, 10 + 10 = 20
        self.assertEqual(result, 20)
    
    def test_unit_conversion(self):
        """単位変換の実行"""
        func = Func(
            id="kWh_to_J",
            dom="Energy_kWh",
            cod="Energy_J",
            impl={"type": "unit_conversion", "factor": 3.6e6}
        )
        
        result = self.executor.execute_func(func, 1.0)
        self.assertEqual(result, 3.6e6)


class TestIntegration(unittest.TestCase):
    """統合テスト"""
    
    def test_cfp_example(self):
        """CFP例題の統合テスト"""
        catalog = parse_dsl_file("catalog.dsl")
        
        # Product -> CO2 のパスを探索
        results = synthesize_backward(catalog, "Product", "CO2")
        
        self.assertGreater(len(results), 0)
        
        # 最短パスを確認
        best = results[0]
        print(f"\nCFP Best Path: {best.proof_string}")
        print(f"  Cost: {best.cost}")
        print(f"  Confidence: {best.confidence:.4f}")
    
    def test_ghg_example(self):
        """GHG例題の統合テスト"""
        catalog = parse_dsl_file("ghg_scope123_product.dsl")
        
        # 各Scopeへのパスを確認
        for scope in ["Scope1Emissions", "Scope2Emissions"]:
            results = synthesize_backward(catalog, "Facility", scope)
            self.assertGreater(len(results), 0, f"No path to {scope}")
        
        # 集約パスを確認
        results = synthesize_backward(catalog, "AllScopesEmissions", "TotalGHGEmissions")
        self.assertGreater(len(results), 0, "No aggregation path")
    
    def test_synthesize_and_execute(self):
        """合成と実行の一括テスト"""
        dsl = '''
type Input
type Middle
type Output

fn step1 {
  sig: Input -> Middle
  impl: formula("y = x * 2")
  cost: 1
}

fn step2 {
  sig: Middle -> Output
  impl: formula("y = x + 100")
  cost: 1
}
'''
        catalog = parse_dsl(dsl)
        
        result = synthesize_and_execute(
            catalog,
            sources=[("Input", 10)],
            goal="Output"
        )
        
        # 10 * 2 = 20, 20 + 100 = 120
        self.assertEqual(result, 120)


def run_tests():
    """テストスイートを実行"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # テストクラスを追加
    suite.addTests(loader.loadTestsFromTestCase(TestDSLParser))
    suite.addTests(loader.loadTestsFromTestCase(TestSynthesisBackward))
    suite.addTests(loader.loadTestsFromTestCase(TestExecutor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # 実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
