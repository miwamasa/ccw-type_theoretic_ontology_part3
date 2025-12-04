# 型理論ベースオントロジー合成システム

型充足（Type Inhabitation）問題をベースに、オントロジー間の変換パスを自動探索・合成するシステム。

## 特徴

- **宣言的なDSL**: 型と関数を宣言的に定義
- **自動パス探索**: Dijkstra的な最小コスト探索
- **多引数関数サポート**: `(A, B, C) -> D` 形式
- **Product型**: 複数の値を1つのタプルとして扱う直積型
- **単位変換**: 自動的な単位変換トランスデューサー
- **実行エンジン**: SPARQL, Formula, REST, Builtinのサポート
- **PROV-O準拠の来歴記録**: 計算過程をW3C標準形式で記録・エクスポート

## インストール

```bash
# 必要なライブラリ（オプション）
pip install requests  # REST API呼び出し用
```

## クイックスタート

### 1. DSLファイルを作成

```dsl
# types.dsl
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

### 2. パスを探索

```bash
python run_dsl.py types.dsl Product CO2
```

### 3. 実行

```bash
python run_dsl.py types.dsl Product CO2 --execute 1000
```

## DSL構文

### 型定義

```dsl
type <型名> [<属性リスト>]

# 例
type Energy [unit=J, range=>=0]
type CO2 [unit=kg]
```

### Product型（直積型）

```dsl
type <型名> = <型1> x <型2> x <型3>

# 例
type AllScopes = Scope1 x Scope2 x Scope3
```

### 関数定義

```dsl
fn <関数名> {
  sig: <ドメイン> -> <コドメイン>
  impl: <実装仕様>
  cost: <コスト>
  confidence: <信頼度>
  inverse_of: <逆関数名>  # オプション
  doc: "説明"             # オプション
}

# 多引数関数
fn aggregate {
  sig: (A, B, C) -> D
  impl: formula("d = a + b + c")
  cost: 1
}
```

### 実装仕様

| タイプ | 構文 | 説明 |
|--------|------|------|
| SPARQL | `sparql("<クエリ>")` | SPARQLクエリを実行 |
| Formula | `formula("<数式>")` | 数式を評価 |
| REST | `rest("<メソッド>, <URL>")` | REST API呼び出し |
| Builtin | `builtin("<名前>")` | 組み込み関数 |

## ファイル構成

```
type_synthesis/
├── synth_lib.py          # コアライブラリ（型、関数、合成アルゴリズム）
├── dsl_parser.py         # DSLパーサー
├── executor.py           # 実行エンジン
├── run_dsl.py            # コマンドラインツール
├── catalog.dsl           # CFP例題
├── ghg_scope123_product.dsl  # GHG例題
├── test_dsl.py           # 統合テスト
└── test_product_type.py  # Product型テスト
```

## アルゴリズム

### 逆方向探索（Backward Search）

ゴール型からソース型へ逆方向に探索し、最小コストのパスを発見。

```
目標: Product -> CO2

探索:
  CO2 <- Fuel <- Energy <- Product
       ↑
  各ステップでコストを累積
  
結果:
  usesEnergy ∘ energyToFuel ∘ fuelToCO2
  コスト: 5, 信頼度: 0.7056
```

### 信頼度計算

パス上の各関数の信頼度の積:

```
Confidence = conf(f₁) × conf(f₂) × ... × conf(fₙ)
```

## テスト実行

```bash
# 全テスト
python test_dsl.py

# Product型テスト
python test_product_type.py
```

## 使用例

### CFP（Carbon Footprint）計算

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
      "confidence_est": 0.8075,
      "steps": [
        {"id": "usesElectricity", "sig": "Product -> ElectricityUsage"},
        {"id": "electricityToCO2", "sig": "ElectricityUsage -> CO2"}
      ],
      "proof": "usesElectricity ∘ electricityToCO2"
    }
  ]
}
```

### GHG Scope 1,2,3 集約

```bash
python test_product_type.py
```

出力:
```
✓ 5/5 テストが成功
🎉 すべてのテストが成功しました！
```

## Python API

```python
from dsl_parser import parse_dsl_file
from synth_lib import synthesize_backward
from executor import execute_synthesis_result, ExecutionContext

# カタログをロード
catalog = parse_dsl_file("catalog.dsl")

# パスを探索
results = synthesize_backward(catalog, "Product", "CO2")

# 実行
context = ExecutionContext()
value = execute_synthesis_result(results[0], input_data, context)
```

## PROV-O準拠の来歴記録（Provenance Tracking）

計算過程をW3C PROV-O標準形式で記録・追跡できます。詳細は[PROVENANCE.md](./PROVENANCE.md)を参照してください。

### 基本的な使い方

```python
from executor import Executor, ExecutionContext

# Provenance追跡を有効化
context = ExecutionContext(track_provenance=True)
executor = Executor(context)

# 実行（自動的にProvenanceが記録される）
result = executor.execute_path(path, 100.0, source_type="Fuel")

# Provenanceグラフを取得
prov_graph = context.provenance_tracker.graph

# 様々な形式でエクスポート
json_output = prov_graph.export_json()
turtle_output = prov_graph.export_turtle()
jsonld_output = prov_graph.export_jsonld()
```

### ユースケース

- **監査とコンプライアンス**: 計算の透明性を確保
- **デバッグと検証**: 計算過程を追跡して問題を特定
- **再現性の確保**: すべての入力・関数・パラメータを記録
- **セマンティックWeb統合**: RDF形式で他ツールと統合

詳細なドキュメントとサンプルコードは[PROVENANCE.md](./PROVENANCE.md)をご覧ください。

## 今後の拡張

1. **DAG構築**: 複数パスの並列実行とマージ
2. **型制約**: 依存型・型制約の導入
3. **ヒューリスティクス**: A*探索の実装
4. **キャッシュ**: 中間結果のキャッシュ

## ライセンス

MIT License
