# GHG Scope 1, 2, 3 集約カタログ
# 温室効果ガス排出量の3つのScopeを集約して総排出量を計算

# =============================================================================
# 型定義
# =============================================================================

# ソース型
type Facility
type Organization

# Scope別排出量
type Scope1Emissions [unit=kg-CO2, range=>=0]
type Scope2Emissions [unit=kg-CO2, range=>=0]
type Scope3Emissions [unit=kg-CO2, range=>=0]

# Product型: 3つのScopeを1つのタプルとして扱う
type AllScopesEmissions = Scope1Emissions x Scope2Emissions x Scope3Emissions

# 集約結果
type TotalGHGEmissions [unit=kg-CO2, range=>=0]

# 中間型
type FuelConsumption [unit=kg, range=>=0]
type ElectricityPurchase [unit=kWh, range=>=0]
type SupplyChainData

# =============================================================================
# Scope 1: 直接排出（燃料燃焼等）
# =============================================================================

fn facilityFuelConsumption {
  sig: Facility -> FuelConsumption
  impl: sparql("SELECT ?f ?fuel WHERE { ?f :fuelConsumption ?fuel }")
  cost: 1
  confidence: 0.95
  doc: "施設の燃料消費量を取得"
}

fn fuelToScope1 {
  sig: FuelConsumption -> Scope1Emissions
  impl: formula("scope1 = fuel * 2.5")
  cost: 1
  confidence: 0.98
  doc: "燃料消費からScope1排出量を計算"
}

# =============================================================================
# Scope 2: 間接排出（購入電力等）
# =============================================================================

fn facilityElectricity {
  sig: Facility -> ElectricityPurchase
  impl: sparql("SELECT ?f ?elec WHERE { ?f :electricityPurchase ?elec }")
  cost: 1
  confidence: 0.9
  doc: "施設の購入電力量を取得"
}

fn electricityToScope2 {
  sig: ElectricityPurchase -> Scope2Emissions
  impl: formula("scope2 = elec * 0.5")
  cost: 1
  confidence: 0.95
  doc: "購入電力からScope2排出量を計算"
}

# =============================================================================
# Scope 3: その他間接排出（サプライチェーン等）
# =============================================================================

fn organizationSupplyChain {
  sig: Organization -> SupplyChainData
  impl: rest("GET, https://api.example.com/supplychain/{id}")
  cost: 3
  confidence: 0.7
  doc: "組織のサプライチェーンデータを取得"
}

fn supplyChainToScope3 {
  sig: SupplyChainData -> Scope3Emissions
  impl: formula("scope3 = value * 1.2")
  cost: 2
  confidence: 0.6
  doc: "サプライチェーンデータからScope3排出量を計算"
}

# Facilityから直接Scope3へのパス（簡易版）
fn facilityToScope3Direct {
  sig: Facility -> Scope3Emissions
  impl: formula("scope3 = 500")
  cost: 5
  confidence: 0.5
  doc: "施設から直接Scope3を推定（簡易計算）"
}

# =============================================================================
# 集約関数
# =============================================================================

# Product型からの集約
fn aggregateAllScopes {
  sig: AllScopesEmissions -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
  confidence: 1.0
  doc: "3つのScopeを合計して総排出量を計算"
}

# 多引数関数版（改善後の理想的な形）
fn aggregateAllScopesMultiArg {
  sig: (Scope1Emissions, Scope2Emissions, Scope3Emissions) -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
  confidence: 1.0
  doc: "3つのScope引数を合計して総排出量を計算"
}

# 単一Scopeのみの集約（問題点の実証用）
fn aggregateScope2Only {
  sig: Scope2Emissions -> TotalGHGEmissions
  impl: formula("total = scope2")
  cost: 0.5
  confidence: 0.3
  doc: "Scope2のみで総排出量を近似（不正確）"
}

# =============================================================================
# 期待されるパス
# =============================================================================
#
# 完全な集約（Product型経由）:
# 
# Facility --> Scope1Emissions ─┐
# Facility --> Scope2Emissions ─┼─> AllScopesEmissions --> TotalGHGEmissions
# Organization -> Scope3Emissions ─┘
#
# コスト計算:
#   Facility -> Scope1: 1 + 1 = 2
#   Facility -> Scope2: 1 + 1 = 2
#   Organization -> Scope3: 3 + 2 = 5
#   AllScopes -> Total: 1
#   合計: 10
#
# 信頼度計算:
#   Scope1: 0.95 * 0.98 = 0.931
#   Scope2: 0.9 * 0.95 = 0.855
#   Scope3: 0.7 * 0.6 = 0.42
#   集約: 1.0
#   合計: 0.931 * 0.855 * 0.42 * 1.0 ≈ 0.334
