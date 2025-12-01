# CFP (Carbon Footprint) 計算カタログ
# 製品のCO2排出量を計算するための型と関数定義

# =============================================================================
# 型定義
# =============================================================================

type Product
type Energy [unit=J, range=>=0]
type Fuel [unit=kg, range=>=0]
type CO2 [unit=kg, range=>=0]

# 追加の中間型
type ElectricityUsage [unit=kWh, range=>=0]
type TransportDistance [unit=km, range=>=0]

# =============================================================================
# 関数定義
# =============================================================================

# 製品からエネルギー使用量を取得
fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?p ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
  doc: "製品のエネルギー使用量を取得"
}

# エネルギーから燃料消費量を推定
fn energyToFuelEstimate {
  sig: Energy -> Fuel
  impl: formula("fuel = energy / efficiency")
  cost: 3
  confidence: 0.8
  inverse_of: fuelToEnergy
  doc: "エネルギー使用量から燃料消費量を推定（効率で割る）"
}

# 燃料消費量からCO2排出量を計算
fn fuelToCO2 {
  sig: Fuel -> CO2
  impl: formula("co2 = fuel * emission_factor")
  cost: 1
  confidence: 0.98
  doc: "燃料消費量からCO2排出量を計算（排出係数をかける）"
}

# 電力使用量からCO2を計算（直接パス）
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
  impl: sparql("SELECT ?p ?e WHERE { ?p :usesElectricity ?e }")
  cost: 1
  confidence: 0.85
  doc: "製品の電力使用量を取得"
}

# 輸送距離からCO2を計算
fn transportToCO2 {
  sig: TransportDistance -> CO2
  impl: formula("co2 = value * 0.1")
  cost: 2
  confidence: 0.7
  doc: "輸送距離からCO2排出量を計算"
}

# 製品から輸送距離を取得
fn productTransport {
  sig: Product -> TransportDistance
  impl: sparql("SELECT ?p ?d WHERE { ?p :transportDistance ?d }")
  cost: 2
  confidence: 0.75
  doc: "製品の輸送距離を取得"
}

# =============================================================================
# 期待されるパス
# =============================================================================
# 
# Product -> CO2 のパス:
# 
# 1. Product --usesEnergy--> Energy --energyToFuelEstimate--> Fuel --fuelToCO2--> CO2
#    コスト: 1 + 3 + 1 = 5
#    信頼度: 0.9 * 0.8 * 0.98 = 0.7056
#
# 2. Product --usesElectricity--> ElectricityUsage --electricityToCO2--> CO2
#    コスト: 1 + 1 = 2
#    信頼度: 0.85 * 0.95 = 0.8075
#
# 3. Product --productTransport--> TransportDistance --transportToCO2--> CO2
#    コスト: 2 + 2 = 4
#    信頼度: 0.75 * 0.7 = 0.525
