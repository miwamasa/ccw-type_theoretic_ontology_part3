# 理論的背景

型理論ベースオントロジー合成システムの理論的基盤について解説します。

## 目次

1. [型理論とは](#型理論とは)
2. [Type Inhabitation問題](#type-inhabitation問題)
3. [Curry-Howard同型対応](#curry-howard同型対応)
4. [オントロジー合成への応用](#オントロジー合成への応用)
5. [探索アルゴリズム](#探索アルゴリズム)

---

## 型理論とは

### 基本概念

**型理論（Type Theory）** は、数学とコンピュータサイエンスにおいて、値を分類するための形式体系です。

#### 型（Type）
値の集合を表す抽象的な概念。例：
- `Int`: 整数の集合
- `String`: 文字列の集合
- `Product`: 製品を表すデータの集合

#### 項（Term）
特定の型に属する具体的な値。例：
- `42 : Int`（42は整数型の項）
- `"Hello" : String`（"Hello"は文字列型の項）

#### 関数型
ある型から別の型への写像を表す型。表記：`A -> B`
- `A`: ドメイン（定義域）
- `B`: コドメイン（値域）

### 型システムの役割

1. **正しさの保証**: 型チェックにより実行前にエラーを検出
2. **ドキュメント**: 型シグネチャが仕様を明示
3. **最適化**: コンパイラが型情報を利用して効率的なコード生成
4. **推論**: 型情報から自動的に処理を構築

---

## Type Inhabitation問題

### 定義

**Type Inhabitation問題**: 与えられた型 `T` に対して、その型を持つ項（値）が存在するかを判定し、もし存在するなら具体的な項を構築する問題。

```
与えられた型: T
問い: ∃ t. (t : T) ?
もし存在するなら: t を構築せよ
```

### 例

#### 単純な例

型環境:
```
f : A -> B
g : B -> C
```

問い: `A -> C` 型の項を構築できるか？

解:
```
λx. g(f(x)) : A -> C
```

合成関数 `g ∘ f` を構築することで、`A -> C` 型を実現できます。

#### 複雑な例（多引数）

型環境:
```
f : A -> B
g : C -> D
h : (B, D) -> E
```

問い: `(A, C) -> E` 型の項を構築できるか？

解:
```
λ(x, y). h(f(x), g(y)) : (A, C) -> E
```

### 計算複雑性

- 単純型付きラムダ計算での Type Inhabitation は **PSPACE完全**
- 実用上は制約を加えることで効率化
  - 最小コストパスの探索
  - 探索深さの制限
  - ヒューリスティクスの導入

---

## Curry-Howard同型対応

### 証明と計算の対応

**Curry-Howard同型対応**: 論理学の証明とプログラムの間の深い対応関係

| 論理 | 型理論 | 計算 |
|------|--------|------|
| 命題 | 型 | 仕様 |
| 証明 | 項（プログラム） | 実装 |
| 含意 A→B | 関数型 A→B | 関数 |
| 連言 A∧B | 直積型 A×B | タプル |
| 選言 A∨B | 直和型 A+B | Either型 |

### 応用

#### 命題の証明 = プログラムの構築

命題: `A ∧ B → C` を証明する

型理論的解釈: `(A, B) -> C` 型の関数を構築する

```
仮定: f : A -> D, g : B -> E, h : (D, E) -> C
結論: λ(x:A, y:B). h(f(x), g(y)) : (A, B) -> C
```

この構成的な証明が、実行可能なプログラムに対応します。

---

## オントロジー合成への応用

### オントロジーとは

**オントロジー**: ドメイン知識を形式的に記述したもの
- 概念（クラス）の階層
- 関係（プロパティ）
- 制約

### 型理論的モデル化

#### オントロジーの型としての解釈

```
オントロジーA = 型 A
オントロジーB = 型 B
変換関数   = 関数 f : A -> B
```

#### 例: カーボンフットプリント

```
型:
  Product    : 製品
  Energy     : エネルギー使用量
  Fuel       : 燃料消費量
  CO2        : CO2排出量

関数:
  usesEnergy       : Product -> Energy
  energyToFuel     : Energy -> Fuel
  fuelToCO2        : Fuel -> CO2
```

目標: `Product -> CO2` のパスを構築

### 合成の利点

1. **宣言的**: 型と関数を定義するだけ
2. **自動**: パス探索を自動化
3. **検証可能**: 型チェックで正しさを保証
4. **拡張可能**: 新しい型・関数を追加するだけで機能拡張

---

## 探索アルゴリズム

### 逆方向探索（Backward Search）

目標型からソース型へ逆向きに探索

#### アルゴリズム概要

```python
def backward_search(goal_type):
    queue = PriorityQueue()
    queue.push((goal_type, [], 0))  # (現在の型, パス, コスト)

    while not queue.empty():
        current, path, cost = queue.pop()

        if current == source_type:
            return path  # 解発見

        # 現在の型をコドメインとする関数を探索
        for func in find_functions_to(current):
            new_cost = cost + func.cost
            new_path = [func] + path

            if func.is_multiarg:
                # 多引数関数の場合、各引数を別々に探索
                for dom in func.domains:
                    queue.push((dom, new_path, new_cost))
            else:
                queue.push((func.domain, new_path, new_cost))
```

#### 探索の可視化

```
目標: Product -> CO2

探索過程:
  CO2 <- [?]
  CO2 <- Fuel [fuelToCO2]
  CO2 <- Energy [energyToFuel, fuelToCO2]
  CO2 <- Product [usesEnergy, energyToFuel, fuelToCO2]  ✓ 解発見

結果: usesEnergy ∘ energyToFuel ∘ fuelToCO2
```

### Dijkstraアルゴリズムとの関係

本システムの探索は Dijkstra の最短経路アルゴリズムの変形です：

| Dijkstra | Type Inhabitation探索 |
|----------|----------------------|
| グラフのノード | 型 |
| エッジ | 関数 |
| 距離 | コスト |
| 最短経路 | 最小コストパス |

### 多引数関数の処理

#### Product型（直積型）

複数の型を組み合わせた型：

```
AllScopes = Scope1 × Scope2 × Scope3
```

タプルとして表現：`(s1, s2, s3)`

#### 多引数関数の探索戦略

```
関数: aggregate : (Scope1, Scope2, Scope3) -> Total

探索:
  1. Total <- (Scope1, Scope2, Scope3) [aggregate]
  2. Scope1 <- Facility [facilityToScope1]
  3. Scope2 <- Facility [facilityToScope2]
  4. Scope3 <- Organization [orgToScope3]

DAG構築:
  Facility ─┬─> Scope1 ─┐
            └─> Scope2 ─┼─> Total
  Organization -> Scope3 ┘
```

### コストと信頼度

#### コスト関数

各関数にコストを割り当て：
```
cost(f) = 計算時間、データ取得コスト、精度の逆数 など
```

パス全体のコスト：
```
cost(path) = Σ cost(f_i)  for f_i in path
```

#### 信頼度

各関数の信頼度を累積：
```
confidence(path) = Π conf(f_i)  for f_i in path
```

信頼度が高く、コストが低いパスを優先。

### 最適化手法

#### ヒューリスティクス

A*探索の導入：
```
f(n) = g(n) + h(n)
```
- `g(n)`: 現在までの実コスト
- `h(n)`: 推定残コスト（ヒューリスティック）

#### キャッシュ

中間結果をキャッシュして再利用：
```
cache: Type -> [(Path, Cost)]
```

#### 枝刈り

- コスト上限による枝刈り
- 探索深さ制限
- 既訪問型の除外（サイクル検出）

---

## 理論の実装へのマッピング

### synth_lib.py

型理論の概念を Python クラスで実装：

```python
@dataclass
class TypeDef:
    """型定義"""
    name: str
    attrs: Dict[str, str]
    schema: Optional[Dict[str, Any]]  # 構造化データスキーマ

@dataclass
class Func:
    """関数定義 (f : A -> B)"""
    id: str
    dom: Union[str, List[str]]  # ドメイン
    cod: str                     # コドメイン
    cost: float
    conf: float
```

### 探索の実装

```python
def synthesize_backward(
    catalog: Catalog,
    source_type: str,
    goal_type: str
) -> List[SynthesisResult]:
    """
    逆方向探索による型合成

    Type Inhabitation問題を解く
    """
    # 優先度付きキューで最小コストパスを探索
    # ...
```

---

## まとめ

本システムは以下の理論的基盤に基づいています：

1. **型理論**: 型と関数による形式的記述
2. **Type Inhabitation**: 型を満たす項の構築問題
3. **Curry-Howard対応**: 証明＝プログラムの対応
4. **グラフ探索**: Dijkstraアルゴリズムによる最適パス発見

これらの理論を組み合わせることで、宣言的なDSLから実行可能なデータ変換パイプラインを自動生成できます。

---

## 参考文献

### 型理論
- Benjamin C. Pierce. "Types and Programming Languages" (2002)
- Morten Heine Sørensen and Pawel Urzyczyn. "Lectures on the Curry-Howard Isomorphism" (2006)

### Type Inhabitation
- Sabine Broda and Luís Damas. "On Long Normal Inhabitants of a Type" (2005)
- José Espírito Santo. "The λ-Calculus and the Unity of Structural Proof Theory" (2008)

### オントロジー
- Thomas R. Gruber. "A Translation Approach to Portable Ontology Specifications" (1993)
- セマンティックWeb標準（RDF, OWL）

### アルゴリズム
- E. W. Dijkstra. "A Note on Two Problems in Connexion with Graphs" (1959)
- Peter Hart, Nils Nilsson, and Bertram Raphael. "A Formal Basis for the Heuristic Determination of Minimum Cost Paths" (1968) - A*アルゴリズム

---

**次へ**: [DSL仕様](dsl-specification.md) | [事例紹介](case-studies.md)
