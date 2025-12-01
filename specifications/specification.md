# 型理論ベースオントロジー合成システム - 仕様書（コンパクト版）

**目的**: この仕様書は、現在のDSLと型システムを別の生成AIで再実装するための材料として作成されました。

## 概要

型理論における**型充足（Type Inhabitation）問題**をベースに、オントロジー間の変換パスを自動探索・合成するシステム。

**コアアイデア**:
- 型を「データ/概念」、関数を「変換」として定義
- `A -> B` のパスを探索することで、Aからどうやって Bを得られるかを自動発見
- Dijkstra的な最小コスト探索で最適パスを選択

---

## 1. DSL言語仕様

### 1.1 型定義

```
type <型名> [<属性リスト>]
```

**例:**
```
type Product
type Energy [unit=J, range=>=0]
type Fuel [unit=kg]
type CO2 [unit=kg]
```

**属性**:
- `unit`: 単位（例: J, kg, kWh, kg-CO2）
- `range`: 値の範囲（例: >=0, >0, 0..100）
- その他カスタム属性も可能

### 1.2 Product型（直積型）

複数の型を1つのタプル型として扱う:

```
type AllScopesEmissions = Scope1Emissions x Scope2Emissions x Scope3Emissions
```

または `×` 記号も使用可能:
```
type AllScopesEmissions = Scope1Emissions × Scope2Emissions × Scope3Emissions
```

**内部表現**: Python のタプルとして実装 `(value1, value2, value3)`

### 1.3 関数定義

```
fn <関数名> {
  sig: <ドメイン型> -> <コドメイン型>
  impl: <実装仕様>
  cost: <コスト（数値）>
  confidence: <信頼度（0.0〜1.0）>
  inverse_of: <逆関数名>（オプション）
  doc: "説明文"（オプション）
}
```

**例:**
```
fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?p ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
}

fn fuelToCO2 {
  sig: Fuel -> CO2
  impl: formula("co2 = fuel_amount * emission_factor")
  cost: 1
  confidence: 0.98
}

fn energyToFuelEstimate {
  sig: Energy -> Fuel
  impl: formula("fuel = energy / efficiency")
  cost: 3
  confidence: 0.8
  inverse_of: fuelToEnergy
}
```

### 1.4 実装仕様（impl）

| タイプ | 構文 | 例 |
|--------|------|-----|
| **SPARQL** | `sparql("<クエリ>")` | `sparql("SELECT ?p ?e WHERE { ?p :usesEnergy ?e }")` |
| **Formula** | `formula("<数式>")` | `formula("co2 = fuel * emission_factor")` |
| **REST** | `rest("<メソッド>, <URL>")` | `rest("GET, https://api.example.com/data/{id}")` |
| **Builtin** | `builtin("<名前>")` | `builtin("product")`, `builtin("sum")`, `builtin("identity")` |

### 1.5 コメント

`#` 以降はコメント:
```
# これは型定義のセクションです
type Product  # 製品型
```

---

## 2. 型充足による合成の仕組み

### 2.1 型理論的基礎

関数定義を**型付け公理（Typing Axioms）**として扱う:

```
Γ ⊢ f : A → B    Γ ⊢ g : B → C
─────────────────────────────── [composition]
Γ ⊢ g ∘ f : A → C
```

目標: `src_type -> goal_type` を満たす**証明項（Proof Term）**= 関数合成を探索

### 2.2 逆方向探索アルゴリズム（Backward Search）

Dijkstra ライクな最短経路探索を、型グラフ上で実行:

```python
def synthesize_backward(catalog, src_type, goal_type, max_cost=100):
    # 優先度付きキュー: (累積コスト, 現在の型, パス)
    pq = [(0.0, goal_type, [])]
    visited_best = {}  # 型 -> 到達した最小コスト
    results = []

    while pq:
        cum_cost, cur_type, path = heapq.heappop(pq)

        # ゴール到達
        if cur_type == src_type:
            results.append((cum_cost, path))
            continue

        # 枝刈り: 既に同じ型により良いコストで到達済み
        if cur_type in visited_best and cum_cost >= visited_best[cur_type]:
            continue
        visited_best[cur_type] = cum_cost

        # 展開: cur_type を返す関数 f を探索
        for f in catalog.funcs_returning(cur_type):
            new_cost = cum_cost + f.cost
            if new_cost > max_cost:
                continue
            new_path = [f] + path  # 前に追加（逆方向のため）
            next_type = f.dom
            heapq.heappush(pq, (new_cost, next_type, new_path))

    return sorted(results, key=lambda x: x[0])
```

**アルゴリズムの特徴**:
- **逆方向**: goal から src へ探索（Backward Reasoning）
- **Dijkstra**: コスト最小のパスを優先
- **枝刈り**: 訪問済み型への重複到達を除去
- **複数解**: コスト制限内のすべてのパスを返す

### 2.3 信頼度（Confidence）の計算

複数関数の合成時、信頼度は積として計算:

```
Path: f₁ ∘ f₂ ∘ f₃
Confidence: conf(f₁) × conf(f₂) × conf(f₃)

例: 0.9 × 0.8 × 0.98 = 0.7056
```

### 2.4 データ構造

**Catalog**:
```python
class Catalog:
    types: Dict[str, dict]           # 型定義
    product_types: Dict[str, ProductType]  # Product型
    funcs: List[Func]                # 関数リスト
    by_cod: Dict[str, List[Func]]    # コドメインでインデックス（逆方向探索用）
    by_dom: Dict[str, List[Func]]    # ドメインでインデックス（前方向探索用）
```

**Func**:
```python
@dataclass
class Func:
    id: str              # 関数名
    dom: str             # ドメイン型
    cod: str             # コドメイン型
    cost: float          # コスト
    conf: float          # 信頼度
    impl: dict           # 実装仕様
    inverse_of: str|None # 逆関数（オプション）
```

---

## 3. 現在の問題点と要リファクタリング事項

### 3.1 Product型の実装が「つぎはぎ」

**問題**:
- Product型は多引数関数の完全サポートの**中間的な解決策**として実装
- 関数は依然として単一入力 `A -> B` のみサポート
- Product型の値（タプル）を**手動で構築**する必要がある

**例（GHG Scope 1,2,3 集約）**:

```python
# 各Scopeを個別に計算（手動）
scope1_value = execute_path(path1, facility_data, context)
scope2_value = execute_path(path2, facility_data, context)
scope3_value = execute_path(path3, org_data, context)

# Product型を手動で構築
allscopes_value = (scope1_value, scope2_value, scope3_value)

# ようやく集約を実行
total = execute_path(aggregation_path, allscopes_value, context)
```

**理想的な実装**（未実装）:
```dsl
fn aggregateAllScopes {
  sig: (Scope1Emissions, Scope2Emissions, Scope3Emissions) -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
}
```

### 3.2 型システムの根本的な制限

1. **単一入力関数のみ**: `A -> B` しかサポートされていない
2. **多引数関数の欠如**: `(A, B, C) -> D` が型レベルでサポートされていない
3. **探索アルゴリズムの制限**: 複数のソース型から1つのゴール型への探索が未実装
4. **実行エンジンのDAG構築**: 複数パスの並列実行やマージが未実装

### 3.3 リファクタリングの方向性

**フェーズ2: 完全な多引数関数サポート**（推定4-6日）:
- 型システムを拡張して `(A, B, C) -> D` をサポート
- 探索アルゴリズムを拡張（複数ソースからの同時探索）
- 実行エンジンにDAG構築・トポロジカルソートを実装
- 型チェックの強化（引数の個数・順序の検証）

**代替案: ワークフロー記述言語**（推定3-4日）:
- YAMLベースのワークフロー定義
- 複数のパス探索ステップを明示的に記述
- 実行順序とデータフローを制御

---

## 4. 拡張機能：トランスデューサー生成

**目的**: 型は一致しているが単位が異なる場合、自動的に単位変換関数を挿入する。

**アイデア**:
```dsl
type Energy1 [unit=J]
type Energy2 [unit=kWh]

# 型充足時、単位が異なることを検出し、自動的に変換関数を挿入:
# J_to_kWh: (value) -> value / 3.6e6
```

**実装アプローチ**:
- 単位変換ルールを事前定義（J ↔ kWh, kg ↔ t, m ↔ km など）
- パス探索時、型は一致するが単位が異なる場合、変換関数をパスに挿入
- 変換関数はコスト 0.1、信頼度 1.0 として扱う（確定的変換）

**利点**:
- 単位の違いによる型ミスマッチを自動解決
- カタログに変換関数を手動で定義する手間を削減
- より柔軟なパス探索が可能

---

## 5. テストケース

### 5.1 CFP（Carbon Footprint）計算例

**DSLファイル**: `type_inhabitation_DSL/catalog.dsl`

**型定義**:
```
type Product
type Energy [unit=J]
type Fuel [unit=kg]
type CO2 [unit=kg]
```

**問題**: Product の CO2 排出量を計算

**発見されるパス**:
```
Product --usesEnergy--> Energy --energyToFuelEstimate--> Fuel --fuelToCO2--> CO2
```

**メトリクス**:
- コスト: 5.0 (1 + 3 + 1)
- 信頼度: 0.7056 (0.9 × 0.8 × 0.98)

**実行コマンド**:
```bash
cd type_inhabitation_DSL
python run_dsl.py catalog.dsl Product CO2
```

**期待される出力**:
```json
{
  "goal": "Product->CO2",
  "plans": [
    {
      "cost": 5.0,
      "confidence_est": 0.7056,
      "steps": [
        {"id": "usesEnergy", "sig": "Product -> Energy", "cost": 1, "conf": 0.9},
        {"id": "energyToFuelEstimate", "sig": "Energy -> Fuel", "cost": 3, "conf": 0.8},
        {"id": "fuelToCO2", "sig": "Fuel -> CO2", "cost": 1, "conf": 0.98}
      ],
      "proof": "usesEnergy ∘ energyToFuelEstimate ∘ fuelToCO2"
    }
  ]
}
```

**学び**:
- 中間型（Energy, Fuel）が自動発見される
- 逆関数（energyToFuelEstimate）が適切に使用される
- コストと信頼度でパスの質が評価される

---

### 5.2 GHGレポート（Scope 1,2,3）集約例

**DSLファイル**: `type_inhabitation_DSL/ghg_scope123_product.dsl`

**問題設定**:
GHG（温室効果ガス）排出量は3つのScopeに分類される:
- **Scope 1**: 直接排出（燃料燃焼等）
- **Scope 2**: 間接排出（購入電力等）
- **Scope 3**: その他間接排出（サプライチェーン等）

**目標**: 3つのScopeの排出量を合計して総排出量を計算

**型定義**:
```dsl
type Facility
type Organization

type Scope1Emissions [unit=kg-CO2]
type Scope2Emissions [unit=kg-CO2]
type Scope3Emissions [unit=kg-CO2]

# Product型で3つのScopeを統合
type AllScopesEmissions = Scope1Emissions x Scope2Emissions x Scope3Emissions

type TotalGHGEmissions [unit=kg-CO2]
```

**集約関数**:
```dsl
fn aggregateAllScopes {
  sig: AllScopesEmissions -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
  confidence: 1.0
}
```

**実行方法（現在の制限により手動）**:
```python
# 1. 各Scopeへのパスを個別に探索・実行
results1 = synthesize_backward(catalog, "Facility", "Scope1Emissions")
scope1_value = execute_path(results1[0][1], facility_data, context)

results2 = synthesize_backward(catalog, "Facility", "Scope2Emissions")
scope2_value = execute_path(results2[0][1], facility_data, context)

results3 = synthesize_backward(catalog, "Organization", "Scope3Emissions")
scope3_value = execute_path(results3[0][1], org_data, context)

# 2. Product型を手動で構築
allscopes_value = (scope1_value, scope2_value, scope3_value)
# 例: (1000.0, 1500.0, 800.0)

# 3. 集約パスを実行
results_final = synthesize_backward(catalog, "AllScopesEmissions", "TotalGHGEmissions")
total_emissions = execute_path(results_final[0][1], allscopes_value, context)
# 結果: 3300.0 kg-CO2
```

**テスト実行**:
```bash
cd type_inhabitation_DSL
python test_product_type.py
```

**期待される出力**:
```
================================================================================
テスト結果サマリー
================================================================================
✓ 5/5 テストが成功

🎉 すべてのテストが成功しました！
```

**問題点の実証**:

**従来のアプローチ（単一Scope経由）**:
```
Facility --[複数パス]--> Scope2Emissions --aggregateScope2Only--> TotalGHGEmissions
```
結果: 1500.0 kg-CO2（Scope2のみ、不正確）

型充足アルゴリズムはコスト最小のパス（Scope2経由）のみを選択してしまう。

**Product型アプローチ**:
```
Facility --> Scope1Emissions ─┐
Facility --> Scope2Emissions ─┼─> AllScopesEmissions --> TotalGHGEmissions
Organization -> Scope3Emissions ─┘
```
結果: 3300.0 kg-CO2（全Scope、正確）

すべてのScopeを明示的に集約することで正確な総排出量を計算。

**学び**:
- 単純なコスト最小化では不十分な場合がある（集約問題）
- Product型により複数パスの統合が可能（中間的解決策）
- 完全な多引数関数サポートが最終的に必要

---

## 6. 実装ファイル構成

```
type_inhabitation_DSL/
├── catalog.dsl                  # CFP例題のDSL
├── ghg_scope123_product.dsl     # GHG例題のDSL（Product型版）
├── dsl_parser.py                # DSLパーサー
├── synth_lib.py                 # 型合成ライブラリ（Catalog, synthesize_backward）
├── executor.py                  # 実行エンジン（SPARQL/REST/Formula/Builtin）
├── run_dsl.py                   # DSL実行スクリプト
├── test_dsl.py                  # DSL統合テスト
└── test_product_type.py         # Product型テスト

doc/
├── dsl_guide.md                 # DSL完全ガイド
├── product_type_guide.md        # Product型ガイド
├── multiarg_implementation_cost_analysis.md  # 多引数関数の実装コスト分析
└── execution_guide.md           # 実行機能ガイド

demo/
├── product_type_demo.html       # Product型インタラクティブデモ（Scratch風）
└── README.md                    # デモ使用方法
```

---

## 7. 再実装時の推奨事項

### 7.1 優先順位

1. **Phase 1**: 基本的な型充足アルゴリズムの実装（逆方向探索、単一入力関数）
2. **Phase 2**: 多引数関数の完全サポート（型システムと探索アルゴリズムの拡張）
3. **Phase 3**: 単位変換トランスデューサー（自動挿入）
4. **Phase 4**: 依存型・型制約（将来の拡張）

### 7.2 設計原則

- **型安全性**: 型チェックを厳密に
- **拡張性**: 新しい impl タイプを簡単に追加できるように
- **分離**: パーサー、型合成、実行を明確に分離
- **テスト駆動**: 各機能に対応するテストケースを用意

### 7.3 注意点

- **探索の効率**: 大規模カタログでは A* やヒューリスティクスが必要
- **循環の検出**: 関数グラフに循環がある場合の対応
- **型の等価性**: 構造的型等価性 vs 名前的型等価性の選択
- **エラーハンドリング**: パース エラー、型エラー、実行エラーの明確な区別

---

## 8. 参考文献

- **型理論**: "Type Theory and Formal Proof" (Nederpelt & Geuvers)
- **圏論**: "Category Theory for Programmers" (Bartosz Milewski)
- **型充足**: "Type Inhabitation" (Wikipedia)
- **Dijkstra**: "A Note on Two Problems in Connexion with Graphs" (Dijkstra, 1959)
- **PROV-O**: W3C Provenance Ontology (https://www.w3.org/TR/prov-o/)

---

## まとめ

本システムは、型理論的な枠組みでオントロジー間の変換パスを自動探索する独自のアプローチを提供します。現在の実装は基本的な機能を提供していますが、特に**多引数関数のサポート**においてリファクタリングが必要です。再実装時には、より型安全で拡張性の高い設計を目指してください。

**コアバリュー**:
- 宣言的な型・関数定義
- 自動的なパス探索
- 型理論・圏論との整合性
- 実用的なメトリクス（コスト・信頼度）