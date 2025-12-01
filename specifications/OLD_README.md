# 型システムとDSLリファクタリング資料

## 概要

このディレクトリには、型理論ベースオントロジー合成システムを**別の生成AIで再実装**するための資料が含まれています。

## 背景

現在の実装は、基本的な型充足アルゴリズムと単一入力関数 (`A -> B`) のサポートを提供していますが、以下の制限があります：

1. **多引数関数の欠如**: `(A, B, C) -> D` の形式がサポートされていない
2. **Product型の中間的実装**: 複数の値を扱うための「つぎはぎ」な解決策
3. **手動での値構築**: Product型の値を手動で組み立てる必要がある

これらの問題を解決するため、型システムとDSLの根本的なリファクタリングが必要です。

## このディレクトリの内容

### SPECIFICATION.md

別の生成AIに渡すための**コンパクトな仕様書**:

1. **DSL言語仕様**: 型定義、関数定義、Product型、実装仕様の構文
2. **型充足による合成の仕組み**: 逆方向探索アルゴリズムの詳細
3. **現在の問題点**: Product型のつぎはぎ実装、多引数関数の欠如
4. **拡張機能**: トランスデューサー生成（単位変換の自動挿入）
5. **テストケース**:
   - CFP計算例（`catalog.dsl`）
   - GHGレポート集約例（`ghg_scope123_product.dsl`）
6. **実装ファイル構成**: 主要ファイルとその役割
7. **再実装時の推奨事項**: 設計原則と注意点

## 使い方

### ステップ1: 仕様書を読む

```bash
cat SPECIFICATION.md
```

### ステップ2: 別の生成AIに仕様書を渡す

```
この仕様書に基づいて、型理論ベースオントロジー合成システムを再実装してください。
特に以下の点を改善してください：

1. 多引数関数の完全サポート: (A, B, C) -> D
2. 探索アルゴリズムの拡張: 複数ソースから1つのゴールへの探索
3. 型システムの整理: Product型をより自然な形で統合
4. 単位変換トランスデューサーの実装

実装言語: Python 3.9+
出力形式: 同じDSL構文をサポート
```

### ステップ3: テストケースで検証

再実装後、以下のテストケースで検証：

```bash
# CFP例題
python run_dsl.py catalog.dsl Product CO2

# GHG例題（理想的には手動構築不要になるべき）
python test_product_type.py
```

## 期待される改善

### Before（現在）

```python
# 各Scopeを個別に実行（手動）
scope1 = execute_path(path1, data1, ctx)
scope2 = execute_path(path2, data2, ctx)
scope3 = execute_path(path3, data3, ctx)

# Product型を手動で構築
allscopes = (scope1, scope2, scope3)

# ようやく集約
total = execute_path(agg_path, allscopes, ctx)
```

### After（リファクタリング後）

```python
# 1回の呼び出しで自動的に複数パスを実行・統合
total = synthesize_and_execute(
    catalog,
    sources=[
        ("Facility", facility_data),
        ("Facility", facility_data),
        ("Organization", org_data)
    ],
    goal="TotalGHGEmissions",
    context=ctx
)
```

または、DSL側で多引数関数を直接定義：

```dsl
fn aggregateAllScopes {
  sig: (Scope1Emissions, Scope2Emissions, Scope3Emissions) -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
}
```