# 型理論ベースオントロジー合成システム

型充足（Type Inhabitation）問題をベースに、オントロジー間の変換パスを自動探索・合成し、実行可能なデータ変換パイプラインを生成するシステム。

[![Tests](https://img.shields.io/badge/tests-36%2F36_passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

## 特徴

### 🎯 宣言的なDSL
型と関数を宣言的に定義するだけで、最適な変換パスを自動探索

### 🔍 自動パス探索
Dijkstraベースの最小コストアルゴリズムで、複数の候補パスから最適解を選択

### 📊 構造化データ生成
**NEW!** 計算結果からJSON/XMLなどの構造化データを動的に生成

### 🔧 多様な実装タイプ
- **Formula**: 数式評価
- **JSON**: 構造化データ生成
- **SPARQL**: セマンティックWeb対応
- **REST API**: 外部サービス連携
- **Builtin**: 組み込み関数

### 🧮 多引数関数サポート
複数のデータソースを統合する`(A, B, C) -> D`形式の関数を完全サポート

## クイックスタート

### インストール

```bash
git clone https://github.com/your-org/type_theoretic_ontology_part3.git
cd type_theoretic_ontology_part3/type_synthesis

# オプション: REST API機能を使う場合
pip install requests
```

### 基本的な使い方

#### 1. DSLファイルを作成

```dsl
# catalog.dsl
type Product
type Energy [unit=J]
type CO2 [unit=kg]

fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
}

fn energyToCO2 {
  sig: Energy -> CO2
  impl: formula("co2 = energy * 0.5")
  cost: 1
  confidence: 0.95
}
```

#### 2. パスを探索

```bash
python run_dsl.py catalog.dsl Product CO2
```

出力:
```json
{
  "goal": "Product->CO2",
  "plans": [
    {
      "cost": 2.0,
      "confidence_est": 0.855,
      "steps": [
        {"id": "usesEnergy", "sig": "Product -> Energy"},
        {"id": "energyToCO2", "sig": "Energy -> CO2"}
      ],
      "proof": "usesEnergy ∘ energyToCO2"
    }
  ]
}
```

#### 3. 実行

```bash
python run_dsl.py catalog.dsl Product CO2 --execute 1000
```

出力:
```
Result: 500.0
```

## 実用例

### CFP（Carbon Footprint）計算

製品のCO2排出量を複数のパスから計算

```bash
python run_dsl.py catalog.dsl Product CO2
# 3つのパスを発見: 電力経由、輸送経由、エネルギー・燃料経由
```

### GHG Scope 1,2,3 統合

複数のGHGスコープを統合して総排出量を計算

```python
from dsl_parser import parse_dsl_file
from synth_lib import synthesize_multiarg_full
from executor import execute_dag, ExecutionContext

catalog = parse_dsl_file("ghg_scope123_product.dsl")
dag = synthesize_multiarg_full(catalog, {
    "s1": "Scope1Emissions",
    "s2": "Scope2Emissions",
    "s3": "Scope3Emissions"
}, "TotalGHGEmissions")

result = execute_dag(dag, {
    "s1": 400.0,
    "s2": 500.0,
    "s3": 800.0
}, ExecutionContext())

print(f"Total: {result} kg-CO2")  # 1700.0 kg-CO2
```

### ChemSHERPA レポート生成

**構造化データ生成の実例**: 化学物質管理データから規制準拠レポートをJSONで生成

```bash
python test_chemsherppa.py
```

生成されるJSON（実際の計算結果から動的に生成）:
```json
{
  "header": {
    "companyName": "ABC電池株式会社",
    "standard": "ChemSHERPA-CI/AI"
  },
  "substances": {
    "lead": {
      "amount": 0.01,
      "concentration": 0.0083,
      "rohs_compliant": true
    },
    "cobalt": {"amount": 60.0, "concentration": 60.0}
  }
}
```

## プロジェクト構成

```
type_synthesis/
├── synth_lib.py           # コアライブラリ（型、関数、合成アルゴリズム）
├── dsl_parser.py          # DSLパーサー
├── executor.py            # 実行エンジン（Formula, JSON, SPARQL, REST）
├── run_dsl.py             # CLIツール
├── catalog.dsl            # CFP計算例
├── ghg_scope123_product.dsl  # GHG Scope統合例
├── chemsherppa_battery.dsl   # ChemSHERPA例
├── test_dsl.py            # 基本テスト（19テスト）
├── test_product_type.py   # Product型テスト（8テスト）
└── test_chemsherppa.py    # ChemSHERPA統合テスト（9テスト）
```

## ドキュメント

- 📖 **[理論](doc/theory.md)** - 型理論とType Inhabitationの背景
- 📝 **[DSL仕様](doc/dsl-specification.md)** - 完全な構文リファレンス
- 💼 **[事例紹介](doc/case-studies.md)** - 実用的なユースケース

## テスト

```bash
# 全テストスイートを実行
python test_dsl.py           # 基本機能テスト（19/19）
python test_product_type.py  # Product型テスト（8/8）
python test_chemsherppa.py   # ChemSHERPA統合テスト（9/9）
```

**全36テストが成功** ✅

## アーキテクチャ

### 型理論的アプローチ

```
型: A, B, C, D
関数: f: A -> B, g: B -> C, h: (C, D) -> E

目標: A -> E を実現したい

探索:
  E から逆方向に探索
  E <- (C, D) [h]
  C <- B [g]
  B <- A [f]
  D が別ソースから提供可能

解: ⟨f ∘ g, source_d⟩ ∘ h
```

### アルゴリズム

- **逆方向探索**: ゴール型からソース型へDijkstra的に探索
- **コスト最小化**: 各関数のコストを累積し、最小コストパスを選択
- **信頼度計算**: パス上の関数の信頼度の積

## 今後の拡張

- [ ] **DAG並列実行**: 複数パスの並列実行とマージ
- [ ] **型制約**: 依存型・型制約の導入
- [ ] **A*探索**: ヒューリスティクスによる探索高速化
- [ ] **キャッシュ**: 中間結果のキャッシュ
- [ ] **XML生成**: テンプレートベースのXML生成

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します！バグ報告や機能リクエストはIssuesへどうぞ。

## 参考文献

- Hindley-Milner型推論
- Curry-Howard同型対応
- Type Inhabitation問題
- セマンティックWeb技術

---

**開発**: Type Theoretic Ontology Project
**バージョン**: 3.0 (Structured Data Support)
