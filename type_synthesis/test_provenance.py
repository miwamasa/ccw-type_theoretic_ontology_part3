"""
Provenance追跡機能のテスト

PROV-O準拠の来歴記録機能が正しく動作することを確認する。
"""

from synth_lib import Catalog, TypeDef, Func, synthesize_backward, synthesize_multiarg_full
from executor import Executor, ExecutionContext
from provenance import ProvenanceGraph, ProvenanceTracker


def test_simple_path_provenance():
    """単純なパスの来歴追跡をテスト"""
    # カタログを構築
    catalog = Catalog()

    # 型定義
    catalog.add_type(TypeDef("Fuel", {"unit": "kg"}))
    catalog.add_type(TypeDef("Energy", {"unit": "MJ"}))
    catalog.add_type(TypeDef("CO2", {"unit": "kg-CO2"}))

    # 関数定義
    catalog.add_func(Func(
        id="fuelToEnergy",
        dom="Fuel",
        cod="Energy",
        cost=1.0,
        conf=0.95,
        impl={"type": "formula", "expr": "value * 42.0"}  # 42 MJ per kg
    ))

    catalog.add_func(Func(
        id="energyToCO2",
        dom="Energy",
        cod="CO2",
        cost=1.0,
        conf=0.90,
        impl={"type": "formula", "expr": "value * 0.0595"}  # 0.0595 kg-CO2 per MJ
    ))

    # パスを合成
    results = synthesize_backward(catalog, "Fuel", "CO2", max_cost=10.0)
    assert len(results) > 0

    path = results[0].path
    print(f"\nSynthesized path: {' -> '.join(f.id for f in path)}")

    # Provenance追跡を有効にして実行
    context = ExecutionContext(track_provenance=True)
    executor = Executor(context)

    # 実行
    input_value = 100.0  # 100 kg of fuel
    result = executor.execute_path(path, input_value, source_type="Fuel")

    print(f"\nInput: {input_value} kg Fuel")
    print(f"Output: {result} kg-CO2")

    # Provenanceグラフを検証
    prov_graph = context.provenance_tracker.graph

    print(f"\nProvenance Graph Statistics:")
    print(f"  Entities: {len(prov_graph.entities)}")
    print(f"  Activities: {len(prov_graph.activities)}")
    print(f"  Usages: {len(prov_graph.usages)}")
    print(f"  Generations: {len(prov_graph.generations)}")
    print(f"  Derivations: {len(prov_graph.derivations)}")

    # エンティティが3つあること（入力、中間、出力）
    assert len(prov_graph.entities) == 3

    # アクティビティが2つあること（fuelToEnergy, energyToCO2）
    assert len(prov_graph.activities) == 2

    # 使用関係が2つあること
    assert len(prov_graph.usages) == 2

    # 生成関係が2つあること
    assert len(prov_graph.generations) == 2

    # 派生関係が2つあること
    assert len(prov_graph.derivations) == 2

    # JSON出力
    print("\n" + "="*60)
    print("JSON Export:")
    print("="*60)
    json_output = prov_graph.export_json()
    print(json_output)

    # Turtle出力
    print("\n" + "="*60)
    print("Turtle Export:")
    print("="*60)
    turtle_output = prov_graph.export_turtle()
    print(turtle_output)

    # JSON-LD出力
    print("\n" + "="*60)
    print("JSON-LD Export:")
    print("="*60)
    jsonld_output = prov_graph.export_jsonld()
    print(jsonld_output)


def test_multiarg_provenance():
    """多引数関数の来歴追跡をテスト"""
    # カタログを構築
    catalog = Catalog()

    # 型定義
    catalog.add_type(TypeDef("Scope1", {"unit": "kg-CO2"}))
    catalog.add_type(TypeDef("Scope2", {"unit": "kg-CO2"}))
    catalog.add_type(TypeDef("Scope3", {"unit": "kg-CO2"}))
    catalog.add_type(TypeDef("TotalGHG", {"unit": "kg-CO2"}))

    # 多引数関数
    catalog.add_func(Func(
        id="aggregateScopes",
        dom=["Scope1", "Scope2", "Scope3"],
        cod="TotalGHG",
        cost=1.0,
        conf=1.0,
        impl={"type": "formula", "expr": "scope1 + scope2 + scope3"}
    ))

    # 合成
    sources = {
        "s1": "Scope1",
        "s2": "Scope2",
        "s3": "Scope3"
    }

    dag = synthesize_multiarg_full(catalog, sources, "TotalGHG", max_cost=10.0)
    assert dag is not None

    print(f"\nSynthesized DAG with {len(dag.nodes)} nodes")

    # Provenance追跡を有効にして実行
    context = ExecutionContext(track_provenance=True)
    executor = Executor(context)

    # 実行
    source_values = {
        "s1": 100.0,
        "s2": 200.0,
        "s3": 300.0
    }

    result = executor.execute_dag(dag, source_values)

    print(f"\nInputs:")
    for k, v in source_values.items():
        print(f"  {k}: {v}")
    print(f"Output: {result} kg-CO2")

    # Provenanceグラフを検証
    prov_graph = context.provenance_tracker.graph

    print(f"\nProvenance Graph Statistics:")
    print(f"  Entities: {len(prov_graph.entities)}")
    print(f"  Activities: {len(prov_graph.activities)}")
    print(f"  Usages: {len(prov_graph.usages)}")
    print(f"  Generations: {len(prov_graph.generations)}")
    print(f"  Derivations: {len(prov_graph.derivations)}")

    # エンティティが4つあること（3つの入力 + 1つの出力）
    assert len(prov_graph.entities) == 4

    # アクティビティが1つあること（aggregateScopes）
    assert len(prov_graph.activities) == 1

    # 使用関係が3つあること（3つの入力）
    assert len(prov_graph.usages) == 3

    # 生成関係が1つあること
    assert len(prov_graph.generations) == 1

    # 派生関係が3つあること（出力は3つの入力から派生）
    assert len(prov_graph.derivations) == 3

    # 系譜を取得
    output_entities = [e for e in prov_graph.entities.values() if e.type_name == "TotalGHG"]
    assert len(output_entities) == 1

    output_id = output_entities[0].id
    lineage = prov_graph.get_entity_lineage(output_id)
    print(f"\nEntity lineage for {output_id}:")
    for ent_id in lineage:
        ent = prov_graph.entities[ent_id]
        print(f"  {ent_id} ({ent.type_name}): {ent.value}")

    # アクティビティチェーンを取得
    activity_chain = prov_graph.get_activity_chain(output_id)
    print(f"\nActivity chain:")
    for act_id in activity_chain:
        act = prov_graph.activities[act_id]
        print(f"  {act_id}: {act.func_id} ({act.func_signature})")

    # Turtle出力
    print("\n" + "="*60)
    print("Turtle Export:")
    print("="*60)
    turtle_output = prov_graph.export_turtle()
    print(turtle_output)


def test_complex_dag_provenance():
    """複雑なDAGの来歴追跡をテスト"""
    # カタログを構築
    catalog = Catalog()

    # 型定義
    catalog.add_type(TypeDef("Fuel", {"unit": "kg"}))
    catalog.add_type(TypeDef("Electricity", {"unit": "kWh"}))
    catalog.add_type(TypeDef("Scope1", {"unit": "kg-CO2"}))
    catalog.add_type(TypeDef("Scope2", {"unit": "kg-CO2"}))
    catalog.add_type(TypeDef("TotalGHG", {"unit": "kg-CO2"}))

    # 関数定義
    catalog.add_func(Func(
        id="fuelToScope1",
        dom="Fuel",
        cod="Scope1",
        cost=1.0,
        conf=0.95,
        impl={"type": "formula", "expr": "value * 2.5"}
    ))

    catalog.add_func(Func(
        id="elecToScope2",
        dom="Electricity",
        cod="Scope2",
        cost=1.0,
        conf=0.90,
        impl={"type": "formula", "expr": "value * 0.5"}
    ))

    catalog.add_func(Func(
        id="aggregateGHG",
        dom=["Scope1", "Scope2"],
        cod="TotalGHG",
        cost=1.0,
        conf=1.0,
        impl={"type": "formula", "expr": "scope1 + scope2"}
    ))

    # 合成
    sources = {
        "fuel_input": "Fuel",
        "elec_input": "Electricity"
    }

    dag = synthesize_multiarg_full(catalog, sources, "TotalGHG", max_cost=10.0)
    assert dag is not None

    print(f"\nSynthesized DAG with {len(dag.nodes)} nodes")
    for node_id, node in dag.nodes.items():
        print(f"  {node_id} ({node.node_type}): {node.type_name}")

    # Provenance追跡を有効にして実行
    context = ExecutionContext(track_provenance=True)
    executor = Executor(context)

    # 実行
    source_values = {
        "fuel_input": 100.0,
        "elec_input": 500.0
    }

    result = executor.execute_dag(dag, source_values)

    print(f"\nInputs:")
    print(f"  Fuel: {source_values['fuel_input']} kg")
    print(f"  Electricity: {source_values['elec_input']} kWh")
    print(f"Output: {result} kg-CO2")

    # Provenanceグラフを検証
    prov_graph = context.provenance_tracker.graph

    print(f"\nProvenance Graph Statistics:")
    print(f"  Entities: {len(prov_graph.entities)}")
    print(f"  Activities: {len(prov_graph.activities)}")
    print(f"  Usages: {len(prov_graph.usages)}")
    print(f"  Generations: {len(prov_graph.generations)}")
    print(f"  Derivations: {len(prov_graph.derivations)}")

    # エンティティ: 入力2つ + 中間2つ + 出力1つ = 5つ
    assert len(prov_graph.entities) == 5

    # アクティビティ: fuelToScope1, elecToScope2, aggregateGHG = 3つ
    assert len(prov_graph.activities) == 3

    # JSON-LD出力
    print("\n" + "="*60)
    print("JSON-LD Export:")
    print("="*60)
    jsonld_output = prov_graph.export_jsonld()
    print(jsonld_output)

    # 系譜を確認
    output_entities = [e for e in prov_graph.entities.values() if e.type_name == "TotalGHG"]
    assert len(output_entities) == 1

    output_id = output_entities[0].id
    lineage = prov_graph.get_entity_lineage(output_id)
    print(f"\nComplete entity lineage:")
    for ent_id in lineage:
        ent = prov_graph.entities[ent_id]
        print(f"  {ent_id} ({ent.type_name}): {ent.value}")


if __name__ == "__main__":
    print("="*60)
    print("Test 1: Simple Path Provenance")
    print("="*60)
    test_simple_path_provenance()

    print("\n\n")
    print("="*60)
    print("Test 2: Multi-argument Function Provenance")
    print("="*60)
    test_multiarg_provenance()

    print("\n\n")
    print("="*60)
    print("Test 3: Complex DAG Provenance")
    print("="*60)
    test_complex_dag_provenance()

    print("\n\nAll tests passed!")
