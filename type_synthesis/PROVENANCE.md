# PROV-O準拠の来歴記録（Provenance Tracking）

## 概要

type_synthesisシステムは、W3C PROV-O標準に準拠した来歴（provenance）記録機能を提供します。この機能により、データ変換の計算過程を詳細に記録し、透明性、追跡可能性、再現性を確保できます。

## PROV-Oとは

PROV-Oは、W3Cが策定したProvenanceオントロジーの標準仕様です。データの起源や生成過程を記録するための共通語彙を提供します。

### 主要な概念

- **Entity（エンティティ）**: データやオブジェクト（入力値、中間結果、出力値）
- **Activity（アクティビティ）**: エンティティを生成・使用・変更する活動（関数適用）
- **Agent（エージェント）**: アクティビティに責任を持つ主体（システム、ユーザー）

### 主要な関係

- **wasGeneratedBy**: エンティティがアクティビティによって生成された
- **used**: アクティビティがエンティティを使用した
- **wasDerivedFrom**: エンティティが別のエンティティから派生した
- **wasAssociatedWith**: アクティビティがエージェントと関連付けられている
- **wasAttributedTo**: エンティティがエージェントに帰属する

## 基本的な使い方

### 1. Provenance追跡の有効化

Provenance追跡を有効にするには、`ExecutionContext`で`track_provenance=True`を設定します。

```python
from executor import Executor, ExecutionContext

# Provenance追跡を有効化
context = ExecutionContext(track_provenance=True)
executor = Executor(context)
```

### 2. 実行とProvenance記録

通常通りに型合成と実行を行うと、自動的にProvenanceが記録されます。

```python
from synth_lib import Catalog, TypeDef, Func, synthesize_backward

# カタログの構築
catalog = Catalog()
catalog.add_type(TypeDef("Fuel", {"unit": "kg"}))
catalog.add_type(TypeDef("CO2", {"unit": "kg-CO2"}))
catalog.add_func(Func(
    id="fuelToCO2",
    dom="Fuel",
    cod="CO2",
    impl={"type": "formula", "expr": "value * 2.5"}
))

# パスの合成
results = synthesize_backward(catalog, "Fuel", "CO2")
path = results[0].path

# 実行（Provenanceが自動的に記録される）
result = executor.execute_path(path, 100.0, source_type="Fuel")
```

### 3. Provenanceグラフの取得

Provenanceグラフは`context.provenance_tracker.graph`からアクセスできます。

```python
prov_graph = context.provenance_tracker.graph

print(f"Entities: {len(prov_graph.entities)}")
print(f"Activities: {len(prov_graph.activities)}")
print(f"Usages: {len(prov_graph.usages)}")
print(f"Generations: {len(prov_graph.generations)}")
```

## エクスポート形式

Provenanceグラフは、複数の標準形式でエクスポートできます。

### JSON形式

```python
json_output = prov_graph.export_json(pretty=True)
print(json_output)
```

出力例：
```json
{
  "namespace": "http://example.org/provenance/",
  "entities": {
    "entity_abc123": {
      "id": "entity_abc123",
      "type": "Entity",
      "prov:type": "Fuel",
      "value": "100.0",
      "prov:generatedAtTime": "2025-12-04T07:15:53.148559"
    }
  },
  "activities": {
    "activity_xyz789": {
      "id": "activity_xyz789",
      "type": "Activity",
      "func_id": "fuelToCO2",
      "func_signature": "Fuel -> CO2",
      "prov:startedAtTime": "2025-12-04T07:15:53.148717"
    }
  }
}
```

### Turtle (RDF)形式

Turtleは、RDFの可読性の高いテキスト形式です。

```python
turtle_output = prov_graph.export_turtle()
print(turtle_output)
```

出力例：
```turtle
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix ex: <http://example.org/provenance/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:entity_abc123 a prov:Entity ;
    prov:type "Fuel" ;
    prov:value "100.0" ;
    prov:generatedAtTime "2025-12-04T07:15:53.148559"^^xsd:dateTime .

ex:activity_xyz789 a prov:Activity ;
    ex:funcId "fuelToCO2" ;
    ex:funcSignature "Fuel -> CO2" ;
    prov:startedAtTime "2025-12-04T07:15:53.148717"^^xsd:dateTime .

ex:activity_xyz789 prov:used ex:entity_abc123 .
ex:entity_def456 prov:wasGeneratedBy ex:activity_xyz789 .
ex:entity_def456 prov:wasDerivedFrom ex:entity_abc123 .
```

### JSON-LD形式

JSON-LDは、JSON形式でLinked Dataを表現する方式です。

```python
jsonld_output = prov_graph.export_jsonld()
print(jsonld_output)
```

出力例：
```json
{
  "@context": {
    "prov": "http://www.w3.org/ns/prov#",
    "ex": "http://example.org/provenance/",
    "Entity": "prov:Entity",
    "Activity": "prov:Activity",
    "used": {"@id": "prov:used", "@type": "@id"},
    "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"}
  },
  "@graph": [
    {
      "@id": "ex:entity_abc123",
      "@type": "Entity",
      "prov:type": "Fuel",
      "prov:value": "100.0"
    }
  ]
}
```

## 高度な使い方

### エンティティの系譜（Lineage）の取得

特定のエンティティがどのエンティティから派生したかを追跡できます。

```python
# 出力エンティティを探す
output_entities = [e for e in prov_graph.entities.values() if e.type_name == "CO2"]
output_id = output_entities[0].id

# 系譜を取得（祖先のリスト）
lineage = prov_graph.get_entity_lineage(output_id)
for ent_id in lineage:
    ent = prov_graph.entities[ent_id]
    print(f"{ent_id} ({ent.type_name}): {ent.value}")
```

### アクティビティチェーンの取得

エンティティを生成したアクティビティのチェーンを取得できます。

```python
activity_chain = prov_graph.get_activity_chain(output_id)
for act_id in activity_chain:
    act = prov_graph.activities[act_id]
    print(f"{act_id}: {act.func_id} ({act.func_signature})")
```

## 多引数関数のProvenance

多引数関数（複数の入力を受け取る関数）の場合、各入力とアクティビティの使用関係が記録されます。

```python
from synth_lib import synthesize_multiarg_full

# 多引数関数のカタログ
catalog = Catalog()
catalog.add_type(TypeDef("Scope1"))
catalog.add_type(TypeDef("Scope2"))
catalog.add_type(TypeDef("Scope3"))
catalog.add_type(TypeDef("TotalGHG"))

catalog.add_func(Func(
    id="aggregateScopes",
    dom=["Scope1", "Scope2", "Scope3"],
    cod="TotalGHG",
    impl={"type": "formula", "expr": "scope1 + scope2 + scope3"}
))

# 合成
sources = {"s1": "Scope1", "s2": "Scope2", "s3": "Scope3"}
dag = synthesize_multiarg_full(catalog, sources, "TotalGHG")

# 実行（Provenance記録）
context = ExecutionContext(track_provenance=True)
executor = Executor(context)
source_values = {"s1": 100.0, "s2": 200.0, "s3": 300.0}
result = executor.execute_dag(dag, source_values)

# Provenanceグラフには3つの入力エンティティと1つの出力エンティティが記録される
prov_graph = context.provenance_tracker.graph
print(f"Entities: {len(prov_graph.entities)}")  # 4
print(f"Usages: {len(prov_graph.usages)}")      # 3
print(f"Derivations: {len(prov_graph.derivations)}")  # 3
```

## 複雑なDAGのProvenance

複数のソースから複数の変換を経てゴールに至る複雑なDAGの場合、すべての中間ステップが記録されます。

```python
# 例: Fuel -> Scope1, Electricity -> Scope2, (Scope1, Scope2) -> TotalGHG
catalog = Catalog()
catalog.add_type(TypeDef("Fuel"))
catalog.add_type(TypeDef("Electricity"))
catalog.add_type(TypeDef("Scope1"))
catalog.add_type(TypeDef("Scope2"))
catalog.add_type(TypeDef("TotalGHG"))

catalog.add_func(Func(
    id="fuelToScope1",
    dom="Fuel",
    cod="Scope1",
    impl={"type": "formula", "expr": "value * 2.5"}
))

catalog.add_func(Func(
    id="elecToScope2",
    dom="Electricity",
    cod="Scope2",
    impl={"type": "formula", "expr": "value * 0.5"}
))

catalog.add_func(Func(
    id="aggregateGHG",
    dom=["Scope1", "Scope2"],
    cod="TotalGHG",
    impl={"type": "formula", "expr": "scope1 + scope2"}
))

# 合成と実行
sources = {"fuel": "Fuel", "elec": "Electricity"}
dag = synthesize_multiarg_full(catalog, sources, "TotalGHG")

context = ExecutionContext(track_provenance=True)
executor = Executor(context)
source_values = {"fuel": 100.0, "elec": 500.0}
result = executor.execute_dag(dag, source_values)

# Provenance: 入力2 + 中間2 + 出力1 = 5エンティティ
# アクティビティ: fuelToScope1, elecToScope2, aggregateGHG = 3アクティビティ
prov_graph = context.provenance_tracker.graph
print(f"Entities: {len(prov_graph.entities)}")      # 5
print(f"Activities: {len(prov_graph.activities)}")  # 3
```

## ユースケース

### 1. 監査とコンプライアンス

Provenanceグラフを保存することで、計算の透明性を確保し、監査に対応できます。

```python
# Provenanceを保存
with open("calculation_provenance.json", "w") as f:
    f.write(prov_graph.export_json())

with open("calculation_provenance.ttl", "w") as f:
    f.write(prov_graph.export_turtle())
```

### 2. デバッグと検証

計算過程を追跡することで、予期しない結果の原因を特定できます。

```python
# どのアクティビティがどの値を生成したかを確認
for gen in prov_graph.generations:
    entity = prov_graph.entities[gen.entity_id]
    activity = prov_graph.activities[gen.activity_id]
    print(f"{activity.func_id} -> {entity.type_name} = {entity.value}")
```

### 3. 再現性の確保

Provenanceグラフには、計算に使用されたすべての入力、関数、パラメータが記録されます。

```python
# 使用された関数の一覧
for activity in prov_graph.activities.values():
    print(f"{activity.func_id}: {activity.func_signature}")
    print(f"  開始: {activity.start_time}")
    print(f"  終了: {activity.end_time}")
```

### 4. セマンティックWeb統合

Turtle/JSON-LD形式でエクスポートすることで、他のセマンティックWebツールと統合できます。

```python
# SPARQL対応のトリプルストアに読み込み可能
turtle_data = prov_graph.export_turtle()
# Apache Jena, RDF4J, Virtuoso などに読み込み
```

## API リファレンス

### ProvenanceGraph

- `add_entity(entity_id, type_name, value, attributes)`: エンティティを追加
- `add_activity(activity_id, func_id, func_signature, attributes)`: アクティビティを追加
- `add_usage(activity_id, entity_id, role)`: 使用関係を追加
- `add_generation(entity_id, activity_id, role)`: 生成関係を追加
- `add_derivation(derived_entity_id, source_entity_id, activity_id)`: 派生関係を追加
- `export_json(pretty=True)`: JSON形式でエクスポート
- `export_turtle()`: Turtle (RDF)形式でエクスポート
- `export_jsonld()`: JSON-LD形式でエクスポート
- `get_entity_lineage(entity_id)`: エンティティの系譜を取得
- `get_activity_chain(entity_id)`: アクティビティチェーンを取得

### ProvenanceTracker

- `track_function_execution(func_id, func_signature, input_entity_ids, output_value, output_type)`: 関数実行を追跡

### ExecutionContext

- `track_provenance: bool`: Provenance追跡を有効化するフラグ
- `provenance_tracker: Optional[ProvenanceTracker]`: ProvenanceTrackerインスタンス

## 参考資料

- [W3C PROV-O Specification](https://www.w3.org/TR/prov-o/)
- [PROV-DM (Data Model)](https://www.w3.org/TR/prov-dm/)
- [PROV Primer](https://www.w3.org/TR/prov-primer/)

## テスト

Provenance機能の完全なテストは`test_provenance.py`にあります。

```bash
python test_provenance.py
```

これにより、以下のテストが実行されます：

1. 単純なパスのProvenance追跡
2. 多引数関数のProvenance追跡
3. 複雑なDAGのProvenance追跡

各テストで、Provenanceグラフが正しく構築され、JSON、Turtle、JSON-LD形式で正しくエクスポートされることを確認します。
