# ChemSHERPA 電池工場 化学物質管理 カタログ
# 調達・製造・輸送フェーズをカバーし、ChemSHERPAレポートを生成

# =============================================================================
# 型定義: 調達フェーズ
# =============================================================================

type RawMaterial                    # 原材料（サプライヤーから調達）
type MaterialWeight [unit=kg]       # 材料重量
type SubstanceRate [unit=%]         # 含有率
type SubstanceAmount [unit=kg]      # 物質含有量

# 個別物質の含有データ
type LithiumContent [unit=kg]       # リチウム含有量
type LeadContent [unit=kg]          # 鉛含有量 (Pb)
type CobaltContent [unit=kg]        # コバルト含有量
type CadmiumContent [unit=kg]       # カドミウム含有量 (Cd)
type VOCContent [unit=kg]           # 揮発性有機化合物

# 調達データ集計
type ProcurementSubstanceData       # 調達フェーズの物質データ

# =============================================================================
# 型定義: 製造フェーズ
# =============================================================================

type ManufacturingInput             # 製造投入データ
type ElectrodeMaterial [unit=kg]    # 電極材料
type ManufacturingLoss [unit=kg]    # 製造ロス
type ProcessedMaterial [unit=kg]    # 加工後材料

# 製造データ集計
type ManufacturingSubstanceData     # 製造フェーズの物質データ

# =============================================================================
# 型定義: 輸送フェーズ
# =============================================================================

type PackagingMaterial [unit=kg]    # 包装材
type ShippingData                   # 出荷データ
type PVCContent [unit=kg]           # PVC含有量

# 輸送データ集計
type ShippingSubstanceData          # 輸送フェーズの物質データ

# =============================================================================
# 型定義: 規制遵守チェック
# =============================================================================

type SubstanceConcentration [unit=%]  # 物質濃度
type RoHSComplianceResult             # RoHS規制遵守結果
type REACHComplianceResult            # REACH規制遵守結果

# =============================================================================
# 型定義: 最終出力
# =============================================================================

# 全フェーズ統合用Product型
type AllPhaseData = ProcurementSubstanceData x ManufacturingSubstanceData x ShippingSubstanceData

type IntegratedSubstanceData        # 統合物質データ
type ChemSHERPAReport               # ChemSHERPA最終レポート

# =============================================================================
# 関数: 調達フェーズ
# =============================================================================

fn extractMaterialWeight {
  sig: RawMaterial -> MaterialWeight
  impl: sparql("SELECT ?m ?w WHERE { ?m :hasWeight ?w }")
  cost: 1
  confidence: 0.95
  doc: "原材料から重量を抽出"
}

fn calculateLeadContent {
  sig: RawMaterial -> LeadContent
  impl: formula("pb = weight * pb_rate / 100")
  cost: 1
  confidence: 0.98
  doc: "鉛含有量を計算 (重量 × 含有率)"
}

fn calculateCobaltContent {
  sig: RawMaterial -> CobaltContent
  impl: formula("co = weight * co_rate / 100")
  cost: 1
  confidence: 0.98
  doc: "コバルト含有量を計算"
}

fn calculateCadmiumContent {
  sig: RawMaterial -> CadmiumContent
  impl: formula("cd = weight * cd_rate / 100")
  cost: 1
  confidence: 0.98
  doc: "カドミウム含有量を計算"
}

fn aggregateProcurementData {
  sig: RawMaterial -> ProcurementSubstanceData
  impl: formula("result = weight * (pb_rate + co_rate + cd_rate) / 100")
  cost: 2
  confidence: 0.95
  doc: "調達フェーズの物質データを集計"
}

# =============================================================================
# 関数: 製造フェーズ
# =============================================================================

fn processElectrodeMaterial {
  sig: ManufacturingInput -> ElectrodeMaterial
  impl: formula("electrode = input_weight * (1 - loss_rate)")
  cost: 2
  confidence: 0.9
  doc: "電極材料を加工（ロス考慮）"
}

fn calculateManufacturingLoss {
  sig: ManufacturingInput -> ManufacturingLoss
  impl: formula("loss = input_weight * loss_rate")
  cost: 1
  confidence: 0.85
  doc: "製造ロスを計算"
}

fn calculateVOCLoss {
  sig: ManufacturingInput -> VOCContent
  impl: formula("voc = voc_amount * (1 - voc_loss_rate)")
  cost: 1
  confidence: 0.8
  doc: "VOCロスを計算（蒸発考慮）"
}

fn aggregateManufacturingData {
  sig: ManufacturingInput -> ManufacturingSubstanceData
  impl: formula("result = input_weight * (1 - loss_rate) + voc_amount * (1 - voc_loss_rate)")
  cost: 2
  confidence: 0.9
  doc: "製造フェーズの物質データを集計"
}

# =============================================================================
# 関数: 輸送フェーズ
# =============================================================================

fn extractPackagingData {
  sig: ShippingData -> PackagingMaterial
  impl: sparql("SELECT ?s ?p WHERE { ?s :hasPackaging ?p }")
  cost: 1
  confidence: 0.95
  doc: "出荷データから包装材データを抽出"
}

fn calculatePVCContent {
  sig: PackagingMaterial -> PVCContent
  impl: formula("pvc = packaging_weight * pvc_rate / 100")
  cost: 1
  confidence: 0.98
  doc: "PVC含有量を計算"
}

fn aggregateShippingData {
  sig: ShippingData -> ShippingSubstanceData
  impl: formula("result = packaging_weight * pvc_rate / 100")
  cost: 2
  confidence: 0.9
  doc: "輸送フェーズの物質データを集計"
}

# =============================================================================
# 関数: 規制遵守チェック
# =============================================================================

fn calculateConcentration {
  sig: IntegratedSubstanceData -> SubstanceConcentration
  impl: formula("concentration = substance_amount / total_weight * 100")
  cost: 1
  confidence: 0.98
  doc: "物質濃度を計算"
}

fn checkRoHSCompliance {
  sig: SubstanceConcentration -> RoHSComplianceResult
  impl: formula("rohs_compliant = concentration < 0.1")
  cost: 1
  confidence: 0.99
  doc: "RoHS規制（閾値0.1%）をチェック"
}

fn checkREACHCompliance {
  sig: SubstanceConcentration -> REACHComplianceResult
  impl: formula("reach_compliant = concentration < 0.1")
  cost: 1
  confidence: 0.99
  doc: "REACH規制（SVHC閾値0.1%）をチェック"
}

# =============================================================================
# 関数: 統合・レポート生成
# =============================================================================

# Product型からの統合
fn integrateAllPhaseData {
  sig: AllPhaseData -> IntegratedSubstanceData
  impl: formula("result = scope1 + scope2 + scope3")
  cost: 2
  confidence: 0.95
  doc: "全フェーズのデータを統合"
}

# 多引数関数版（改善版）
fn integrateAllPhaseDataMultiArg {
  sig: (ProcurementSubstanceData, ManufacturingSubstanceData, ShippingSubstanceData) -> IntegratedSubstanceData
  impl: formula("result = scope1 + scope2 + scope3")
  cost: 2
  confidence: 0.95
  doc: "全フェーズのデータを統合（多引数版）"
}

fn generateChemSHERPAReport {
  sig: IntegratedSubstanceData -> ChemSHERPAReport
  impl: formula("report = value * 1.0")
  cost: 3
  confidence: 0.9
  doc: "ChemSHERPA XMLレポートを生成"
}

# 統合からレポートへの直接パス
fn integratedToReport {
  sig: AllPhaseData -> ChemSHERPAReport
  impl: formula("report = scope1 + scope2 + scope3")
  cost: 5
  confidence: 0.85
  doc: "統合データから直接レポート生成"
}

# =============================================================================
# 期待されるパス
# =============================================================================
#
# 完全な合成（多引数関数使用）:
#
# RawMaterial ──────→ ProcurementSubstanceData ──┐
# ManufacturingInput → ManufacturingSubstanceData ┼→ IntegratedSubstanceData → ChemSHERPAReport
# ShippingData ──────→ ShippingSubstanceData ────┘
#
# proof: ⟨aggregateProcurementData, aggregateManufacturingData, aggregateShippingData⟩ 
#        ∘ integrateAllPhaseDataMultiArg 
#        ∘ generateChemSHERPAReport
