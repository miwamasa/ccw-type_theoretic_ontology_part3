# DSL仕様

型理論ベースオントロジー合成システムのDSL（Domain Specific Language）の完全な仕様です。

## 目次

1. [概要](#概要)
2. [型定義](#型定義)
3. [関数定義](#関数定義)
4. [実装タイプ](#実装タイプ)
5. [コメント](#コメント)
6. [完全な例](#完全な例)

---

## 概要

### 基本構文

DSLファイルは以下の2つの要素で構成されます：

1. **型定義** (`type`)
2. **関数定義** (`fn`)

### ファイルフォーマット

- エンコーディング: UTF-8
- 拡張子: `.dsl`
- コメント: `#` で始まる行

---

## 型定義

### 基本型

#### 構文

```dsl
type <型名> [<属性リスト>]
```

#### 例

```dsl
type Product
type Energy [unit=J, range=>=0]
type CO2 [unit=kg, range=>=0]
type Temperature [unit=celsius, range=-273.15..1000]
```

#### 属性

型には任意の属性を付与できます：

| 属性 | 説明 | 例 |
|------|------|-----|
| `unit` | 単位 | `unit=kg`, `unit=kWh` |
| `range` | 値域 | `range=>=0`, `range=0..100` |
| `format` | データ形式 | `format=iso8601` |

### Product型（直積型）

複数の型を組み合わせた型を定義できます。

#### 構文

```dsl
type <型名> = <型1> x <型2> x <型3> ...
```

または

```dsl
type <型名> = <型1> × <型2> × <型3> ...
```

#### 例

```dsl
type AllScopes = Scope1Emissions x Scope2Emissions x Scope3Emissions
type Location = Latitude × Longitude
type RGBColor = Red x Green x Blue
```

#### 実行時の表現

Product型はタプルとして実行されます：

```python
# AllScopes型の値
value = (100.0, 200.0, 300.0)  # (Scope1, Scope2, Scope3)
```

---

## 関数定義

### 基本構文

```dsl
fn <関数名> {
  sig: <シグネチャ>
  impl: <実装仕様>
  cost: <コスト>
  confidence: <信頼度>
  inverse_of: <逆関数名>  # オプション
  doc: "<説明>"           # オプション
}
```

### 必須フィールド

#### sig (シグネチャ)

関数の型シグネチャを定義します。

**単引数関数**:
```dsl
sig: SourceType -> TargetType
```

**多引数関数**:
```dsl
sig: (Type1, Type2, Type3) -> TargetType
```

#### impl (実装仕様)

関数の実装方法を指定します。詳細は[実装タイプ](#実装タイプ)を参照。

#### cost (コスト)

関数の実行コスト（浮動小数点数）。パス探索時の評価に使用されます。

```dsl
cost: 1      # 低コスト
cost: 5      # 中程度
cost: 10     # 高コスト
```

#### confidence (信頼度)

関数の信頼度（0.0〜1.0）。パス全体の信頼度は各関数の信頼度の積になります。

```dsl
confidence: 0.95   # 高信頼
confidence: 0.8    # 中程度
confidence: 0.5    # 低信頼
```

### オプションフィールド

#### inverse_of (逆関数)

逆関数を指定します。双方向の変換が可能な場合に使用。

```dsl
fn celsiusToFahrenheit {
  sig: Celsius -> Fahrenheit
  impl: formula("f = c * 9/5 + 32")
  cost: 1
  confidence: 1.0
  inverse_of: fahrenheitToCelsius
}

fn fahrenheitToCelsius {
  sig: Fahrenheit -> Celsius
  impl: formula("c = (f - 32) * 5/9")
  cost: 1
  confidence: 1.0
  inverse_of: celsiusToFahrenheit
}
```

#### doc (ドキュメント)

関数の説明文。

```dsl
fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
  doc: "製品のエネルギー使用量をSPARQLで取得"
}
```

### 多引数関数

複数の入力を受け取る関数を定義できます。

```dsl
fn aggregateScopes {
  sig: (Scope1Emissions, Scope2Emissions, Scope3Emissions) -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
  confidence: 1.0
  doc: "3つのスコープを合計"
}
```

---

## 実装タイプ

関数の実装方法を指定します。

### 1. formula - 数式評価

数式を評価して結果を計算します。

#### 構文

```dsl
impl: formula("<数式>")
```

#### 例

```dsl
fn energyToCO2 {
  sig: Energy -> CO2
  impl: formula("co2 = energy * 0.5")
  cost: 1
  confidence: 0.95
}
```

#### 利用可能な変数

**単引数関数**:
- `value`, `input`, `x`: 入力値
- 式内の任意の変数名（自動マッピング）

**多引数関数**:
- `arg0`, `arg1`, `arg2`, ...: 各引数
- `scope1`, `scope2`, `scope3`: 3引数の場合の特別な名前

**数式内の関数**:
- 算術演算: `+`, `-`, `*`, `/`, `**`
- 数学関数: `abs()`, `round()`, `min()`, `max()`, `sum()`, `sqrt()`, `log()`, `exp()`
- 三角関数: `sin()`, `cos()`, `tan()`

### 2. json - JSON生成

**NEW!** 構造化データをJSONとして生成します。

#### 構文

```dsl
impl: json({<スキーマ>})
```

#### スキーマ

JSONスキーマは、キーと値のペアで構成されます。値には以下を指定できます：

- **文字列**: 式として評価される
- **数値・真偽値**: そのまま使用
- **オブジェクト**: ネストされたJSON
- **配列**: リスト

#### 例

```dsl
fn aggregateProcurementData {
  sig: RawMaterial -> ProcurementSubstanceData
  impl: json({
    "pb_amount": "weight * pb_rate / 100",
    "co_amount": "weight * co_rate / 100",
    "cd_amount": "weight * cd_rate / 100"
  })
  cost: 2
  confidence: 0.95
}
```

#### 複雑な例（ネスト）

```dsl
fn generateReport {
  sig: AllPhaseData -> ChemSHERPAReport
  impl: json({
    "header": {
      "companyName": "ABC Corporation",
      "standard": "ChemSHERPA-CI/AI"
    },
    "substances": {
      "lead": {
        "amount": "arg0['pb_amount']",
        "concentration": "arg0['pb_amount'] / arg1['electrode_weight'] * 100",
        "rohs_compliant": "arg0['pb_amount'] / arg1['electrode_weight'] * 100 < 0.1"
      }
    },
    "compliance": {
      "rohs": true,
      "reach": true
    }
  })
  cost: 5
  confidence: 0.85
}
```

#### 式の評価

スキーマ内の文字列は Python 式として評価されます：

```json
{
  "value": "x * 2",              // 計算結果
  "condition": "x > 0",          // 真偽値
  "nested": "arg0['field']",     // ネストされたフィールドアクセス
  "check": "x if x > 0 else 0"   // 条件式
}
```

利用可能な組み込み関数：
- `isinstance()`, `dict()`, `list()`, `tuple()`, `dir()`
- `abs()`, `round()`, `min()`, `max()`, `sum()`, `len()`
- `str()`, `int()`, `float()`

### 3. template - テンプレート生成

テンプレート文字列からXML/JSONを生成します。

#### 構文

```dsl
impl: template("<テンプレート文字列>", {<マッピング>})
```

#### 例

```dsl
fn generateXML {
  sig: ProductData -> XMLReport
  impl: template(
    "<Product><Name>{{name}}</Name><Weight>{{weight}}</Weight></Product>",
    {
      "name": "product_name",
      "weight": "weight_kg"
    }
  )
  cost: 3
  confidence: 0.9
}
```

### 4. sparql - SPARQLクエリ

セマンティックWebのSPARQLクエリを実行します。

#### 構文

```dsl
impl: sparql("<SPARQLクエリ>")
```

#### 例

```dsl
fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
}
```

#### プレースホルダー

クエリ内で入力値を使用できます：

```dsl
impl: sparql("SELECT ?value WHERE { ?id :hasValue ?value FILTER(?id = {id}) }")
```

- `{key}`: 辞書のキー
- `{value}`: 値そのもの

### 5. rest - REST API

REST APIを呼び出します。

#### 構文

```dsl
impl: rest("<メソッド>, <URL>")
```

#### 例

```dsl
fn fetchWeatherData {
  sig: Location -> WeatherData
  impl: rest("GET, https://api.weather.com/data?lat={lat}&lon={lon}")
  cost: 5
  confidence: 0.8
}
```

#### サポートされるメソッド

- `GET`: データ取得
- `POST`: データ送信（入力値をJSON bodyとして送信）

### 6. builtin - 組み込み関数

システムに組み込まれた関数を使用します。

#### 構文

```dsl
impl: builtin("<関数名>")
```

#### 利用可能な組み込み関数

| 関数名 | 説明 | 例 |
|--------|------|-----|
| `identity` | 入力をそのまま返す | `x -> x` |
| `sum` | リスト/タプルの合計 | `[1,2,3] -> 6` |
| `product` | リスト/タプルの積 | `[2,3,4] -> 24` |
| `average` | リスト/タプルの平均 | `[1,2,3] -> 2` |
| `first` | 最初の要素 | `[1,2,3] -> 1` |
| `last` | 最後の要素 | `[1,2,3] -> 3` |
| `count` | 要素数 | `[1,2,3] -> 3` |
| `abs` | 絶対値 | `-5 -> 5` |
| `round` | 四捨五入 | `3.7 -> 4` |

#### 例

```dsl
fn passThrough {
  sig: A -> A
  impl: builtin("identity")
  cost: 0
  confidence: 1.0
}

fn calculateAverage {
  sig: DataList -> AverageValue
  impl: builtin("average")
  cost: 1
  confidence: 1.0
}
```

---

## コメント

### 行コメント

`#` で始まる行はコメントとして扱われます。

```dsl
# これはコメントです
type Product  # 行末コメント
```

### ブロックコメント

複数行のコメントは各行を `#` で始めます。

```dsl
# =============================================================================
# CFP (Carbon Footprint) 計算カタログ
# 製品のCO2排出量を計算するための型と関数定義
# =============================================================================
```

---

## 完全な例

### CFP計算システム

```dsl
# =============================================================================
# CFP (Carbon Footprint) 計算システム
# =============================================================================

# 型定義
type Product
type Energy [unit=J, range=>=0]
type Fuel [unit=kg, range=>=0]
type CO2 [unit=kg, range=>=0]
type ElectricityUsage [unit=kWh, range=>=0]

# 関数定義

# 製品からエネルギー使用量を取得
fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
  doc: "製品のエネルギー使用量をSPARQLで取得"
}

# エネルギーから燃料消費量を推定
fn energyToFuel {
  sig: Energy -> Fuel
  impl: formula("fuel = energy / efficiency")
  cost: 3
  confidence: 0.8
  inverse_of: fuelToEnergy
  doc: "エネルギー使用量から燃料消費量を推定"
}

# 燃料消費量からCO2排出量を計算
fn fuelToCO2 {
  sig: Fuel -> CO2
  impl: formula("co2 = fuel * emission_factor")
  cost: 1
  confidence: 0.98
  doc: "燃料消費量からCO2排出量を計算"
}

# 電力使用量からCO2を直接計算
fn electricityToCO2 {
  sig: ElectricityUsage -> CO2
  impl: formula("co2 = value * kWh_to_CO2")
  cost: 1
  confidence: 0.95
  doc: "電力使用量からCO2排出量を直接計算"
}

# 製品から電力使用量を取得
fn usesElectricity {
  sig: Product -> ElectricityUsage
  impl: sparql("SELECT ?e WHERE { ?p :usesElectricity ?e }")
  cost: 1
  confidence: 0.85
  doc: "製品の電力使用量を取得"
}
```

### GHG Scope統合システム

```dsl
# =============================================================================
# GHG Scope 1,2,3 統合システム
# =============================================================================

# 型定義
type Facility
type Organization
type Scope1Emissions [unit=kg-CO2]
type Scope2Emissions [unit=kg-CO2]
type Scope3Emissions [unit=kg-CO2]
type TotalGHGEmissions [unit=kg-CO2]

# Product型
type AllScopes = Scope1Emissions x Scope2Emissions x Scope3Emissions

# 関数定義

fn facilityToScope1 {
  sig: Facility -> Scope1Emissions
  impl: formula("scope1 = fuel * emission_factor")
  cost: 2
  confidence: 0.9
}

fn facilityToScope2 {
  sig: Facility -> Scope2Emissions
  impl: formula("scope2 = elec * grid_factor")
  cost: 2
  confidence: 0.95
}

fn organizationToScope3 {
  sig: Organization -> Scope3Emissions
  impl: rest("GET, https://api.scope3.io/emissions?org={org_id}")
  cost: 5
  confidence: 0.7
}

# 多引数関数で3つのスコープを統合
fn aggregateAllScopes {
  sig: (Scope1Emissions, Scope2Emissions, Scope3Emissions) -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
  confidence: 1.0
  doc: "3つのGHGスコープを合計"
}
```

### 化学物質情報伝達レポート生成

```dsl
# =============================================================================
# 化学物質情報伝達レポート生成システム
# =============================================================================

# 型定義
type RawMaterial
type ManufacturingInput
type ShippingData
type ProcurementSubstanceData
type ManufacturingSubstanceData
type ShippingSubstanceData
type ChemSHERPAReport

# Product型
type AllPhaseData = ProcurementSubstanceData x ManufacturingSubstanceData x ShippingSubstanceData

# 関数定義

# JSON生成の例
fn aggregateProcurementData {
  sig: RawMaterial -> ProcurementSubstanceData
  impl: json({
    "pb_amount": "weight * pb_rate / 100",
    "co_amount": "weight * co_rate / 100",
    "cd_amount": "weight * cd_rate / 100"
  })
  cost: 2
  confidence: 0.95
}

fn aggregateManufacturingData {
  sig: ManufacturingInput -> ManufacturingSubstanceData
  impl: json({
    "electrode_weight": "input_weight * (1 - loss_rate)",
    "loss_amount": "input_weight * loss_rate",
    "voc_loss": "voc_amount * voc_loss_rate"
  })
  cost: 2
  confidence: 0.9
}

fn integratedToReport {
  sig: AllPhaseData -> ChemSHERPAReport
  impl: json({
    "header": {
      "companyName": "ABC Corporation",
      "standard": "ChemSHERPA-CI/AI"
    },
    "substances": {
      "lead": {
        "amount": "arg0['pb_amount']",
        "concentration": "arg0['pb_amount'] / arg1['electrode_weight'] * 100",
        "rohs_compliant": "arg0['pb_amount'] / arg1['electrode_weight'] * 100 < 0.1"
      }
    }
  })
  cost: 5
  confidence: 0.85
}
```

---

## ベストプラクティス

### 1. 型の命名

- 明確で説明的な名前を使用
- PascalCase（先頭大文字）を推奨
- 単位を持つ型には `[unit=...]` 属性を付与

```dsl
type Energy [unit=J]        # Good
type e [unit=J]             # Bad: 短すぎる
type energy_value [unit=J]  # OK: snake_caseも可
```

### 2. 関数の命名

- 動詞または動詞句を使用
- camelCaseを推奨
- 意味が明確になるように命名

```dsl
fn energyToCO2           # Good: 変換を明示
fn calculate             # Bad: 何を計算するか不明
fn getEnergyFromProduct  # Good: 詳細な説明
```

### 3. コストの設定

実際の計算コストを反映させる：

```dsl
cost: 1   # メモリ内の計算、簡単な数式
cost: 2-5 # データベースクエリ、中程度の計算
cost: 5-10# REST API呼び出し、複雑な計算
```

### 4. 信頼度の設定

データの信頼性を反映：

```dsl
confidence: 0.95-1.0  # 公式な統計データ、確実な計算
confidence: 0.8-0.95  # 一般的なデータソース
confidence: 0.5-0.8   # 推定値、外部API
```

### 5. ドキュメント

複雑な関数には必ずdocを付ける：

```dsl
fn complexCalculation {
  sig: A -> B
  impl: formula("...")
  cost: 5
  confidence: 0.8
  doc: "この関数は〇〇を計算します。入力は△△の形式で、出力は××になります。"
}
```

---

## まとめ

DSLの主要な要素：

1. **型定義**: `type` で型を宣言
2. **関数定義**: `fn` で関数を宣言
3. **実装タイプ**: `formula`, `json`, `sparql`, `rest`, `builtin`, `template`
4. **Product型**: `x` または `×` で直積型を定義
5. **多引数関数**: `(A, B, C) -> D` で複数入力を処理

---

**次へ**: [理論](theory.md) | [事例紹介](case-studies.md)
