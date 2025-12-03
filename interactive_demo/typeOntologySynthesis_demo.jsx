import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  ArrowRight,
  Play,
  Settings,
  Database,
  Code,
  Layers,
  CheckCircle,
  AlertCircle,
  TrendingUp,
  Activity,
  Zap,
  Box,
  Trash2,
  Plus,
  X,
  FileText,
  HelpCircle
} from 'lucide-react';

// --- Types ---

type TypeDef = {
  name: string;
  attrs: Record<string, string>;
  isProduct: boolean;
  components: string[]; // For product types A x B
};

type FuncImpl = {
  type: 'formula' | 'json' | 'sparql' | 'rest' | 'builtin' | 'template';
  value: string;
};

type FuncDef = {
  name: string;
  dom: string[]; // Domain (inputs)
  cod: string;   // Codomain (output)
  cost: number;
  confidence: number;
  impl: FuncImpl;
  doc?: string;
};

type Catalog = {
  types: Record<string, TypeDef>;
  funcs: FuncDef[];
};

type SynthesisNode = {
  type: string;
  func?: FuncDef; // The function used to produce this type
  inputs: SynthesisNode[]; // The input nodes required by the function
  accumulatedCost: number;
  accumulatedConfidence: number;
};

// --- Example DSLs ---

const EXAMPLES = {
  "基本例": {
    dsl: `# 基本的なCFP計算例

type Product
type Energy [unit=J]
type CO2 [unit=kg]

fn usesEnergy {
  sig: Product -> Energy
  impl: formula("energy = value * 1.0")
  cost: 1
  confidence: 0.9
  doc: "製品のエネルギー使用量"
}

fn energyToCO2 {
  sig: Energy -> CO2
  impl: formula("co2 = energy * 0.5")
  cost: 1
  confidence: 0.95
  doc: "エネルギーからCO2排出量を計算"
}`,
    inputData: {
      "Product": 1000,
      "Energy": 1000
    },
    source: "Product",
    target: "CO2"
  },

  "CFP計算": {
    dsl: `# CFP (Carbon Footprint) 計算

type Product
type Energy [unit=J, range=>=0]
type Fuel [unit=kg, range=>=0]
type CO2 [unit=kg, range=>=0]
type ElectricityUsage [unit=kWh, range=>=0]

fn usesEnergy {
  sig: Product -> Energy
  impl: formula("energy = value * 1.0")
  cost: 1
  confidence: 0.9
  doc: "製品のエネルギー使用量を取得"
}

fn energyToFuel {
  sig: Energy -> Fuel
  impl: formula("fuel = energy / 0.35")
  cost: 3
  confidence: 0.8
  doc: "エネルギーから燃料消費量を推定"
}

fn fuelToCO2 {
  sig: Fuel -> CO2
  impl: formula("co2 = fuel * 2.5")
  cost: 1
  confidence: 0.98
  doc: "燃料消費量からCO2排出量を計算"
}

fn usesElectricity {
  sig: Product -> ElectricityUsage
  impl: formula("elec = value * 0.8")
  cost: 1
  confidence: 0.85
  doc: "製品の電力使用量を取得"
}

fn electricityToCO2 {
  sig: ElectricityUsage -> CO2
  impl: formula("co2 = value * 0.5")
  cost: 1
  confidence: 0.95
  doc: "電力使用量からCO2排出量を計算"
}`,
    inputData: {
      "Product": 1000,
      "Energy": 1000,
      "ElectricityUsage": 800
    },
    source: "Product",
    target: "CO2"
  },

  "GHG Scope統合": {
    dsl: `# GHG Scope 1,2,3 統合

type Facility
type Scope1Emissions [unit=kg-CO2]
type Scope2Emissions [unit=kg-CO2]
type Scope3Emissions [unit=kg-CO2]
type TotalGHGEmissions [unit=kg-CO2]

fn facilityToScope1 {
  sig: Facility -> Scope1Emissions
  impl: formula("scope1 = fuel * 2.5")
  cost: 2
  confidence: 0.9
  doc: "Scope1直接排出"
}

fn facilityToScope2 {
  sig: Facility -> Scope2Emissions
  impl: formula("scope2 = elec * 0.5")
  cost: 2
  confidence: 0.95
  doc: "Scope2間接排出"
}

fn facilityToScope3 {
  sig: Facility -> Scope3Emissions
  impl: formula("scope3 = value * 0.3")
  cost: 5
  confidence: 0.7
  doc: "Scope3その他排出"
}

fn aggregateScopes {
  sig: Scope1Emissions, Scope2Emissions, Scope3Emissions -> TotalGHGEmissions
  impl: formula("total = arg0 + arg1 + arg2")
  cost: 1
  confidence: 1.0
  doc: "3つのスコープを合計"
}`,
    inputData: {
      "Facility": { "fuel": 400, "elec": 3000 },
      "Scope1Emissions": 1000,
      "Scope2Emissions": 1500,
      "Scope3Emissions": 120
    },
    source: "Facility",
    target: "TotalGHGEmissions"
  },

  "化学物質情報伝達": {
    dsl: `# 化学物質情報伝達レポート生成

type RawMaterial
type ProcurementData
type ManufacturingData
type ComplianceReport

fn aggregateProcurement {
  sig: RawMaterial -> ProcurementData
  impl: formula("data = weight * 0.01")
  cost: 2
  confidence: 0.95
  doc: "調達フェーズデータ集計"
}

fn aggregateManufacturing {
  sig: ProcurementData -> ManufacturingData
  impl: formula("mfg = value * 0.8")
  cost: 2
  confidence: 0.9
  doc: "製造フェーズデータ集計"
}

fn generateReport {
  sig: ManufacturingData -> ComplianceReport
  impl: formula("report = value * 1.0")
  cost: 3
  confidence: 0.85
  doc: "規制準拠レポート生成"
}`,
    inputData: {
      "RawMaterial": { "weight": 100, "pb_rate": 0.01 },
      "ProcurementData": 1.0,
      "ManufacturingData": 0.8
    },
    source: "RawMaterial",
    target: "ComplianceReport"
  }
};

const DEFAULT_EXAMPLE = "CFP計算";
const DEFAULT_DSL = EXAMPLES[DEFAULT_EXAMPLE].dsl;
const DEFAULT_INPUT_DATA = JSON.stringify(EXAMPLES[DEFAULT_EXAMPLE].inputData, null, 2);

// --- Parser Logic (Phase 1) ---

const parseDSL = (text: string): Catalog => {
  const types: Record<string, TypeDef> = {};
  const funcs: FuncDef[] = [];

  const lines = text.split('\n');
  let i = 0;

  while (i < lines.length) {
    let line = lines[i].trim();

    // Skip empty lines and comments
    if (!line || line.startsWith('#')) {
      i++;
      continue;
    }

    // Parse type definition
    if (line.startsWith('type ')) {
      const typeStr = line.substring(5).trim();

      // Check for Product Type: type AllScopes = A x B x C
      // Must distinguish from attributes: type CO2 [unit=kg]
      // Product type has '=' before any '[', or no '[' at all
      const bracketPos = typeStr.indexOf('[');
      const equalsPos = typeStr.indexOf('=');
      const isProductType = equalsPos !== -1 && (bracketPos === -1 || equalsPos < bracketPos);

      if (isProductType) {
        const [name, componentStr] = typeStr.split('=').map(s => s.trim());
        const components = componentStr.split(/\s*[x×]\s*/).map(s => s.trim());
        types[name] = {
          name,
          attrs: {},
          isProduct: true,
          components
        };
      } else {
        // Basic type: type TypeName [attr1=val1, attr2=val2]
        const match = typeStr.match(/^(\w+)(?:\s*\[([^\]]+)\])?/);
        if (match) {
          const name = match[1];
          const attrsStr = match[2];
          const attrs: Record<string, string> = {};

          if (attrsStr) {
            attrsStr.split(',').forEach(pair => {
              const [key, val] = pair.split('=').map(s => s.trim());
              if (key && val) attrs[key] = val;
            });
          }

          types[name] = {
            name,
            attrs,
            isProduct: false,
            components: []
          };
        }
      }
      i++;
    }
    // Parse function definition
    else if (line.startsWith('fn ') && line.includes('{')) {
      // fn funcName {
      const funcName = line.substring(3, line.indexOf('{')).trim();
      i++;

      let sig = '';
      let implType = 'builtin';
      let implValue = '';
      let cost = 1.0;
      let confidence = 1.0;
      let doc = '';

      // Read function block
      while (i < lines.length) {
        line = lines[i].trim();

        if (line === '}') {
          i++;
          break;
        }

        if (line.startsWith('sig:')) {
          sig = line.substring(4).trim();
        } else if (line.startsWith('impl:')) {
          const implStr = line.substring(5).trim();
          // Parse impl: formula("...") or impl: sparql("..."), etc
          const implMatch = implStr.match(/(\w+)\s*\(\s*"([^"]*)"\s*\)/);
          if (implMatch) {
            implType = implMatch[1];
            implValue = implMatch[2];
          }
        } else if (line.startsWith('cost:')) {
          cost = parseFloat(line.substring(5).trim());
        } else if (line.startsWith('confidence:')) {
          confidence = parseFloat(line.substring(11).trim());
        } else if (line.startsWith('doc:')) {
          doc = line.substring(4).trim().replace(/^["']|["']$/g, '');
        }

        i++;
      }

      // Parse signature: A -> B or (A, B) -> C or A, B -> C
      if (sig) {
        let dom: string[] = [];
        let cod = '';

        if (sig.includes('->')) {
          const [domStr, codStr] = sig.split('->').map(s => s.trim());
          cod = codStr;

          // Check if domain is multi-arg: (A, B) or A, B
          const cleanDom = domStr.replace(/^\(|\)$/g, '').trim();
          if (cleanDom.includes(',')) {
            dom = cleanDom.split(',').map(s => s.trim()).filter(s => s);
          } else {
            dom = [cleanDom];
          }
        }

        funcs.push({
          name: funcName,
          dom,
          cod,
          cost,
          confidence,
          impl: { type: implType, value: implValue },
          doc
        });
      }
    }
    else {
      i++;
    }
  }

  return { types, funcs };
};

// --- Solver Logic (Phase 2 - Backward Search) ---

const solveInhabitation = (
  targetType: string,
  sourceTypes: string[],
  catalog: Catalog,
  depth = 0,
  maxDepth = 5
): SynthesisNode[] => {
  // Base case: Target is one of the sources
  if (sourceTypes.includes(targetType)) {
    return [{
      type: targetType,
      inputs: [],
      accumulatedCost: 0,
      accumulatedConfidence: 1.0
    }];
  }

  if (depth >= maxDepth) return [];

  const candidates: SynthesisNode[] = [];

  // Find functions that produce the target type
  const potentialFuncs = catalog.funcs.filter(f => f.cod === targetType);

  for (const f of potentialFuncs) {
    // Recursively solve for all inputs (domain) of the function
    const inputSolutions: SynthesisNode[][] = [];
    let possible = true;

    for (const inputType of f.dom) {
      const subSolutions = solveInhabitation(inputType, sourceTypes, catalog, depth + 1, maxDepth);
      if (subSolutions.length === 0) {
        possible = false;
        break;
      }
      inputSolutions.push(subSolutions);
    }

    if (possible) {
      // Cartesian product of input solutions (simplification: taking best combinations or flattening)
      // For this demo, we'll try to combine the first found valid path for each input to keep it simple,
      // but in a real system we'd generate all permutations.
      
      // Let's generate one candidate per function combining the "best" sub-solutions
      // Simple heuristic: Take the first solution found for each input
      const selectedInputs = inputSolutions.map(sols => sols[0]); 
      
      const totalCost = selectedInputs.reduce((sum, node) => sum + node.accumulatedCost, 0) + f.cost;
      const totalConf = selectedInputs.reduce((prod, node) => prod * node.accumulatedConfidence, 1) * f.confidence;

      candidates.push({
        type: targetType,
        func: f,
        inputs: selectedInputs,
        accumulatedCost: totalCost,
        accumulatedConfidence: totalConf
      });
    }
  }

  return candidates.sort((a, b) => {
    // Sort by Cost asc, then Confidence desc
    if (Math.abs(a.accumulatedCost - b.accumulatedCost) > 0.001) {
      return a.accumulatedCost - b.accumulatedCost;
    }
    return b.accumulatedConfidence - a.accumulatedConfidence;
  });
};

// --- Execution Engine (Phase 3) ---

const executePipeline = (node: SynthesisNode, context: any): any => {
  // Leaf node (Source)
  if (!node.func) {
    return context[node.type];
  }

  // Execute inputs
  const inputValues = node.inputs.map(inputNode => executePipeline(inputNode, context));

  // Execute current function
  const f = node.func;
  
  // Simulation Logic based on impl type
  switch (f.impl.type) {
    case 'formula':
      // Parse and evaluate formula
      // Safety: In a real app, do not use Function/eval loosely.
      try {
        // Remove variable assignment if present (e.g., "energy = value * 1.0" -> "value * 1.0")
        let formula = f.impl.value;
        const assignMatch = formula.match(/^\s*\w+\s*=\s*(.+)$/);
        if (assignMatch) {
          formula = assignMatch[1];
        }

        // Build scope: add properties from input objects
        const scope: Record<string, any> = {};
        inputValues.forEach((val, idx) => {
          scope[`arg${idx}`] = val;
          // If input is an object, spread its properties into scope
          if (typeof val === 'object' && val !== null) {
            Object.assign(scope, val);
          }
        });

        // Special handling for single input: make it available as "value"
        if (inputValues.length === 1) {
          scope.value = inputValues[0];
        }

        // Create function with scope
        const scopeKeys = Object.keys(scope);
        const scopeValues = Object.values(scope);
        const funcBody = `return (${formula})`;

        // eslint-disable-next-line no-new-func
        const fn = new Function(...scopeKeys, funcBody);
        return fn(...scopeValues);
      } catch (e) {
        return `Error evaluating formula: ${e instanceof Error ? e.message : String(e)}`;
      }
    case 'rest':
    case 'sparql':
      // Mock: look up in context by function name if available, else return random/dummy
      if (context[f.name] !== undefined) return context[f.name];
      return 100; // Mock default
    default:
      return "Executed";
  }
};

// --- Components ---

// Help Modal Component
const HelpModal = ({ isOpen, onClose, topic }: {
  isOpen: boolean;
  onClose: () => void;
  topic: 'dsl' | 'synthesis' | 'execution' | 'blocks';
}) => {
  if (!isOpen) return null;

  const helpContent = {
    dsl: {
      title: 'DSL 文法ガイド',
      content: (
        <>
          <h3 className="font-bold text-md mb-2">型定義 (Type)</h3>
          <div className="bg-slate-100 p-2 rounded mb-3 font-mono text-xs">
            <div>type TypeName</div>
            <div>type TypeName [attr1=value1, attr2=value2]</div>
            <div>type ProductType = TypeA x TypeB x TypeC</div>
          </div>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><strong>基本型</strong>: <code>type Product</code></li>
            <li><strong>属性付き型</strong>: <code>type Energy [unit=J, range=&gt;=0]</code></li>
            <li><strong>積型</strong>: <code>type AllScopes = Scope1 x Scope2 x Scope3</code></li>
          </ul>

          <h3 className="font-bold text-md mb-2">関数定義 (Function)</h3>
          <div className="bg-slate-100 p-2 rounded mb-3 font-mono text-xs">
            <div>fn functionName &#123;</div>
            <div>  sig: InputType -&gt; OutputType</div>
            <div>  impl: formula("expression")</div>
            <div>  cost: 1.0</div>
            <div>  confidence: 0.95</div>
            <div>  doc: "説明"</div>
            <div>&#125;</div>
          </div>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><strong>sig</strong>: 関数の型シグネチャ（入力 → 出力）</li>
            <li><strong>impl</strong>: 実装方式（formula/json/sparql/rest）</li>
            <li><strong>cost</strong>: 実行コスト（数値）</li>
            <li><strong>confidence</strong>: 信頼度（0.0〜1.0）</li>
          </ul>

          <h3 className="font-bold text-md mb-2">複数入力関数</h3>
          <div className="bg-slate-100 p-2 rounded mb-3 font-mono text-xs">
            <div>sig: TypeA, TypeB, TypeC -&gt; OutputType</div>
            <div>impl: formula("arg0 + arg1 + arg2")</div>
          </div>
        </>
      )
    },
    blocks: {
      title: 'ブロックエディタの使い方',
      content: (
        <>
          <h3 className="font-bold text-md mb-2 flex items-center gap-2">
            <div className="bg-blue-500 text-white px-2 py-1 rounded text-xs">type</div>
            型ブロック
          </h3>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><strong>型名</strong>を直接編集可能</li>
            <li><strong>Product Type</strong>チェックで積型に変換</li>
            <li><strong>属性</strong>を追加・編集・削除（key=value形式）</li>
            <li>右上の<Trash2 size={12} className="inline"/>で削除</li>
          </ul>

          <h3 className="font-bold text-md mb-2 flex items-center gap-2">
            <div className="bg-purple-500 text-white px-2 py-1 rounded text-xs">fn</div>
            関数ブロック
          </h3>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><strong>関数名</strong>を直接編集</li>
            <li><strong>Signature</strong>: 入力型 → 出力型（カンマ区切りで複数入力可）</li>
            <li><strong>Implementation</strong>: 実装タイプと式を指定</li>
            <li><strong>Cost/Confidence</strong>: コストと信頼度を調整</li>
          </ul>

          <h3 className="font-bold text-md mb-2">操作</h3>
          <ul className="list-disc ml-5 text-sm space-y-1">
            <li><strong>Add Type/Function</strong>ボタンで追加</li>
            <li><strong>Text/Blocksボタン</strong>でモード切替</li>
            <li>ブロック編集はDSLテキストに自動反映</li>
          </ul>
        </>
      )
    },
    synthesis: {
      title: 'パス探索とは',
      content: (
        <>
          <h3 className="font-bold text-md mb-2">型居住問題 (Type Inhabitation)</h3>
          <p className="mb-3 text-sm">
            ソース型からゴール型への変換経路を、定義された関数を組み合わせて自動的に探索します。
            これは型理論における<strong>型居住問題</strong>の解決です。
          </p>

          <h3 className="font-bold text-md mb-2">探索アルゴリズム</h3>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><strong>後方推論</strong>: ゴール型から逆向きに探索</li>
            <li><strong>コスト最小化</strong>: 最もコストの低いパスを優先</li>
            <li><strong>信頼度計算</strong>: パス全体の信頼度を乗算で算出</li>
            <li><strong>複数解</strong>: 異なるパスがあれば全て列挙</li>
          </ul>

          <h3 className="font-bold text-md mb-2">探索例</h3>
          <div className="bg-slate-100 p-3 rounded mb-3 text-xs">
            <div className="font-bold mb-2">Product → CO2 を探索</div>
            <div className="flex items-center gap-2 mb-1">
              <span className="bg-emerald-100 px-2 py-1 rounded">Product</span>
              <ArrowRight size={12} />
              <span className="bg-blue-100 px-2 py-1 rounded">usesEnergy</span>
              <ArrowRight size={12} />
              <span className="bg-indigo-100 px-2 py-1 rounded">Energy</span>
              <ArrowRight size={12} />
              <span className="bg-blue-100 px-2 py-1 rounded">energyToCO2</span>
              <ArrowRight size={12} />
              <span className="bg-emerald-100 px-2 py-1 rounded">CO2</span>
            </div>
            <div className="text-slate-600 mt-2">
              Cost: 2.0, Confidence: 85.5%
            </div>
          </div>

          <h3 className="font-bold text-md mb-2">パス選択</h3>
          <p className="text-sm">
            複数のパスが見つかった場合、<strong>最もコストが低く、信頼度が高い</strong>パスが「Best」として推奨されます。
          </p>
        </>
      )
    },
    execution: {
      title: '実行と結果の見方',
      content: (
        <>
          <h3 className="font-bold text-md mb-2">実行の仕組み</h3>
          <p className="mb-3 text-sm">
            選択したパスに沿って、関数を順番に実行します。
            各関数は入力値を受け取り、<code>impl</code>で定義された式を評価して出力を生成します。
          </p>

          <h3 className="font-bold text-md mb-2">入力データ形式</h3>
          <div className="bg-slate-100 p-2 rounded mb-3 font-mono text-xs">
            <div>&#123;</div>
            <div>  "SourceType": value,</div>
            <div>  "SourceType": &#123; "prop1": val1, "prop2": val2 &#125;</div>
            <div>&#125;</div>
          </div>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><strong>数値</strong>: <code>"Product": 1000</code></li>
            <li><strong>オブジェクト</strong>: <code>"Facility": &#123; "fuel": 400, "elec": 3000 &#125;</code></li>
          </ul>

          <h3 className="font-bold text-md mb-2">Formula実装での変数</h3>
          <ul className="list-disc ml-5 mb-4 text-sm space-y-1">
            <li><code>value</code>: 単一入力の値</li>
            <li><code>arg0, arg1, arg2</code>: 複数入力の各値</li>
            <li><code>fuel, elec, weight</code>: 入力オブジェクトのプロパティ</li>
          </ul>

          <h3 className="font-bold text-md mb-2">結果の表示</h3>
          <div className="bg-emerald-50 border border-emerald-200 p-2 rounded text-sm mb-2">
            <span className="text-slate-600 font-bold">Result:</span>
            <span className="text-emerald-600 ml-2 font-mono">2620</span>
          </div>
          <p className="text-sm">
            最終的な計算結果が表示されます。エラーの場合はエラーメッセージが表示されます。
          </p>
        </>
      )
    }
  };

  const content = helpContent[topic];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-blue-50">
          <h2 className="text-lg font-bold text-blue-900 flex items-center gap-2">
            <HelpCircle size={20} />
            {content.title}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-700"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">
          {content.content}
        </div>
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
};

// Block Editor Components
const TypeBlock = ({ typeDef, onUpdate, onDelete }: {
  typeDef: TypeDef;
  onUpdate: (updated: TypeDef) => void;
  onDelete: () => void;
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const addAttribute = () => {
    const newAttrs = { ...typeDef.attrs, [`attr${Object.keys(typeDef.attrs).length + 1}`]: '' };
    onUpdate({ ...typeDef, attrs: newAttrs });
  };

  const updateAttribute = (oldKey: string, newKey: string, value: string) => {
    const newAttrs = { ...typeDef.attrs };
    delete newAttrs[oldKey];
    newAttrs[newKey] = value;
    onUpdate({ ...typeDef, attrs: newAttrs });
  };

  const deleteAttribute = (key: string) => {
    const newAttrs = { ...typeDef.attrs };
    delete newAttrs[key];
    onUpdate({ ...typeDef, attrs: newAttrs });
  };

  return (
    <div className="bg-blue-50 border-2 border-blue-300 rounded-lg p-3 mb-2 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 flex-1">
          <div className="bg-blue-500 text-white px-2 py-1 rounded text-xs font-bold">type</div>
          <input
            type="text"
            value={typeDef.name}
            onChange={(e) => onUpdate({ ...typeDef, name: e.target.value })}
            className="flex-1 bg-white border border-blue-300 rounded px-2 py-1 text-sm font-bold"
            placeholder="TypeName"
          />
        </div>
        <button onClick={onDelete} className="text-red-500 hover:text-red-700 ml-2">
          <Trash2 size={16} />
        </button>
      </div>

      {isExpanded && (
        <div className="ml-6 space-y-2">
          {/* Product Type Option */}
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={typeDef.isProduct}
              onChange={(e) => onUpdate({ ...typeDef, isProduct: e.target.checked })}
              className="rounded"
            />
            <span>Product Type (A × B)</span>
          </label>

          {typeDef.isProduct ? (
            <div>
              <label className="text-xs text-slate-600">Components (comma-separated):</label>
              <input
                type="text"
                value={typeDef.components.join(', ')}
                onChange={(e) => onUpdate({ ...typeDef, components: e.target.value.split(',').map(s => s.trim()) })}
                className="w-full bg-white border border-blue-200 rounded px-2 py-1 text-sm mt-1"
                placeholder="TypeA, TypeB, TypeC"
              />
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-slate-600">Attributes:</label>
                <button onClick={addAttribute} className="text-blue-600 hover:text-blue-800">
                  <Plus size={14} />
                </button>
              </div>
              {Object.entries(typeDef.attrs).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2 mb-1">
                  <input
                    type="text"
                    value={key}
                    onChange={(e) => updateAttribute(key, e.target.value, value)}
                    className="w-1/3 bg-white border border-blue-200 rounded px-2 py-1 text-xs"
                    placeholder="key"
                  />
                  <span className="text-xs">=</span>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => updateAttribute(key, key, e.target.value)}
                    className="flex-1 bg-white border border-blue-200 rounded px-2 py-1 text-xs"
                    placeholder="value"
                  />
                  <button onClick={() => deleteAttribute(key)} className="text-red-500 hover:text-red-700">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const FunctionBlock = ({ funcDef, onUpdate, onDelete }: {
  funcDef: FuncDef;
  onUpdate: (updated: FuncDef) => void;
  onDelete: () => void;
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="bg-purple-50 border-2 border-purple-300 rounded-lg p-3 mb-2 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 flex-1">
          <div className="bg-purple-500 text-white px-2 py-1 rounded text-xs font-bold">fn</div>
          <input
            type="text"
            value={funcDef.name}
            onChange={(e) => onUpdate({ ...funcDef, name: e.target.value })}
            className="flex-1 bg-white border border-purple-300 rounded px-2 py-1 text-sm font-bold"
            placeholder="functionName"
          />
        </div>
        <button onClick={onDelete} className="text-red-500 hover:text-red-700 ml-2">
          <Trash2 size={16} />
        </button>
      </div>

      {isExpanded && (
        <div className="ml-6 space-y-2">
          {/* Signature */}
          <div>
            <label className="text-xs text-slate-600">Signature (domain → codomain):</label>
            <div className="flex items-center gap-2 mt-1">
              <input
                type="text"
                value={funcDef.dom.join(', ')}
                onChange={(e) => onUpdate({ ...funcDef, dom: e.target.value.split(',').map(s => s.trim()).filter(s => s) })}
                className="flex-1 bg-white border border-purple-200 rounded px-2 py-1 text-xs"
                placeholder="InputType1, InputType2"
              />
              <span className="text-xs">→</span>
              <input
                type="text"
                value={funcDef.cod}
                onChange={(e) => onUpdate({ ...funcDef, cod: e.target.value })}
                className="flex-1 bg-white border border-purple-200 rounded px-2 py-1 text-xs"
                placeholder="OutputType"
              />
            </div>
          </div>

          {/* Implementation */}
          <div>
            <label className="text-xs text-slate-600">Implementation:</label>
            <div className="flex items-center gap-2 mt-1">
              <select
                value={funcDef.impl.type}
                onChange={(e) => onUpdate({ ...funcDef, impl: { ...funcDef.impl, type: e.target.value as any } })}
                className="bg-white border border-purple-200 rounded px-2 py-1 text-xs"
              >
                <option value="formula">formula</option>
                <option value="json">json</option>
                <option value="sparql">sparql</option>
                <option value="rest">rest</option>
                <option value="builtin">builtin</option>
              </select>
              <input
                type="text"
                value={funcDef.impl.value}
                onChange={(e) => onUpdate({ ...funcDef, impl: { ...funcDef.impl, value: e.target.value } })}
                className="flex-1 bg-white border border-purple-200 rounded px-2 py-1 text-xs font-mono"
                placeholder="implementation expression"
              />
            </div>
          </div>

          {/* Cost & Confidence */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-slate-600">Cost:</label>
              <input
                type="number"
                step="0.1"
                value={funcDef.cost}
                onChange={(e) => onUpdate({ ...funcDef, cost: parseFloat(e.target.value) || 0 })}
                className="w-full bg-white border border-purple-200 rounded px-2 py-1 text-xs"
              />
            </div>
            <div>
              <label className="text-xs text-slate-600">Confidence:</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={funcDef.confidence}
                onChange={(e) => onUpdate({ ...funcDef, confidence: parseFloat(e.target.value) || 0 })}
                className="w-full bg-white border border-purple-200 rounded px-2 py-1 text-xs"
              />
            </div>
          </div>

          {/* Documentation */}
          <div>
            <label className="text-xs text-slate-600">Documentation:</label>
            <input
              type="text"
              value={funcDef.doc || ''}
              onChange={(e) => onUpdate({ ...funcDef, doc: e.target.value })}
              className="w-full bg-white border border-purple-200 rounded px-2 py-1 text-xs"
              placeholder="説明を入力"
            />
          </div>
        </div>
      )}
    </div>
  );
};

const BlockEditor = ({ types, funcs, onUpdate }: {
  types: TypeDef[];
  funcs: FuncDef[];
  onUpdate: (types: TypeDef[], funcs: FuncDef[]) => void;
}) => {
  const addType = () => {
    const newType: TypeDef = {
      name: `NewType${types.length + 1}`,
      attrs: {},
      isProduct: false,
      components: []
    };
    onUpdate([...types, newType], funcs);
  };

  const addFunction = () => {
    const newFunc: FuncDef = {
      name: `newFunc${funcs.length + 1}`,
      dom: [],
      cod: '',
      cost: 1,
      confidence: 1,
      impl: { type: 'formula', value: '' },
      doc: ''
    };
    onUpdate(types, [...funcs, newFunc]);
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 bg-slate-50">
      {/* Types Section */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
            <Box size={14} />
            Types
          </h3>
          <button
            onClick={addType}
            className="flex items-center gap-1 px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
          >
            <Plus size={12} />
            Add Type
          </button>
        </div>
        {types.map((type, idx) => (
          <TypeBlock
            key={idx}
            typeDef={type}
            onUpdate={(updated) => {
              const newTypes = [...types];
              newTypes[idx] = updated;
              onUpdate(newTypes, funcs);
            }}
            onDelete={() => {
              const newTypes = types.filter((_, i) => i !== idx);
              onUpdate(newTypes, funcs);
            }}
          />
        ))}
      </div>

      {/* Functions Section */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
            <Settings size={14} />
            Functions
          </h3>
          <button
            onClick={addFunction}
            className="flex items-center gap-1 px-2 py-1 bg-purple-500 text-white rounded text-xs hover:bg-purple-600"
          >
            <Plus size={12} />
            Add Function
          </button>
        </div>
        {funcs.map((func, idx) => (
          <FunctionBlock
            key={idx}
            funcDef={func}
            onUpdate={(updated) => {
              const newFuncs = [...funcs];
              newFuncs[idx] = updated;
              onUpdate(types, newFuncs);
            }}
            onDelete={() => {
              const newFuncs = funcs.filter((_, i) => i !== idx);
              onUpdate(types, newFuncs);
            }}
          />
        ))}
      </div>
    </div>
  );
};

const GraphVisualizer = ({ catalog }: { catalog: Catalog }) => {
  // Improved graph layout with proper multi-argument function support
  const typeNames = Object.keys(catalog.types);
  const nodeRadius = 35;
  const viewWidth = 800;
  const viewHeight = 500;

  // Layered layout: arrange types in layers based on dependencies
  const typePositions: Record<string, {x: number, y: number}> = {};

  // Simple horizontal layout with vertical spread
  typeNames.forEach((typeName, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    typePositions[typeName] = {
      x: 100 + col * 200,
      y: 80 + row * 120
    };
  });

  return (
    <div className="relative w-full h-full bg-white overflow-hidden border border-slate-200 rounded-lg flex items-center justify-center p-4 shadow-sm">
      <div className="text-slate-400 absolute top-2 right-2 text-xs">カタロググラフ (type_synthesis互換)</div>

      <svg className="w-full h-full" viewBox={`0 0 ${viewWidth} ${viewHeight}`}>
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#64748b" />
          </marker>
        </defs>

        {/* Render edges (functions) first so they appear below nodes */}
        {catalog.funcs.map((f, i) => {
          const endType = f.cod;
          const endPos = typePositions[endType];

          if (!endPos) return null;

          // Handle multi-argument functions: draw edges from all domain types
          return (
            <g key={`func-${i}`}>
              {f.dom.map((domType, domIdx) => {
                const startPos = typePositions[domType];
                if (!startPos) return null;

                // Calculate edge points (from node edge to node edge, not center to center)
                const dx = endPos.x - startPos.x;
                const dy = endPos.y - startPos.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const offsetStart = nodeRadius / dist;
                const offsetEnd = nodeRadius / dist;

                const x1 = startPos.x + dx * offsetStart;
                const y1 = startPos.y + dy * offsetStart;
                const x2 = endPos.x - dx * offsetEnd;
                const y2 = endPos.y - dy * offsetEnd;

                const midX = (x1 + x2) / 2;
                const midY = (y1 + y2) / 2;

                return (
                  <g key={`edge-${i}-${domIdx}`}>
                    <line
                      x1={x1} y1={y1}
                      x2={x2} y2={y2}
                      stroke="#94a3b8"
                      strokeWidth="2"
                      markerEnd="url(#arrowhead)"
                      opacity="0.7"
                    />
                    {/* Function name label (only on first edge to avoid clutter) */}
                    {domIdx === 0 && (
                      <>
                        <text
                          x={midX} y={midY - 12}
                          fill="#475569"
                          fontSize="9"
                          fontWeight="bold"
                          textAnchor="middle"
                        >
                          {f.name}
                        </text>
                        {/* Cost and confidence labels */}
                        <text
                          x={midX} y={midY - 2}
                          fill="#64748b"
                          fontSize="8"
                          textAnchor="middle"
                        >
                          cost: {f.cost} | conf: {(f.confidence * 100).toFixed(0)}%
                        </text>
                      </>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}

        {/* Render nodes (types) */}
        {typeNames.map((typeName) => {
          const pos = typePositions[typeName];
          const typeDef = catalog.types[typeName];
          const hasAttrs = Object.keys(typeDef.attrs).length > 0;

          return (
            <g key={typeName}>
              {/* Node circle */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={nodeRadius}
                fill={typeDef.isProduct ? "#fef3c7" : "#dbeafe"}
                stroke={typeDef.isProduct ? "#f59e0b" : "#3b82f6"}
                strokeWidth="2.5"
              />
              {/* Type name */}
              <text
                x={pos.x}
                y={pos.y}
                dy="4"
                textAnchor="middle"
                fill="#1e293b"
                fontSize="11"
                fontWeight="bold"
              >
                {typeName.length > 12 ? typeName.substring(0, 10) + '...' : typeName}
              </text>
              {/* Attributes badge */}
              {hasAttrs && (
                <text
                  x={pos.x}
                  y={pos.y + 15}
                  textAnchor="middle"
                  fill="#64748b"
                  fontSize="7"
                >
                  [{Object.entries(typeDef.attrs).slice(0, 1).map(([k, v]) => `${k}=${v}`).join(', ')}]
                </text>
              )}
              {/* Product type indicator */}
              {typeDef.isProduct && (
                <text
                  x={pos.x}
                  y={pos.y - 20}
                  textAnchor="middle"
                  fill="#f59e0b"
                  fontSize="8"
                  fontWeight="bold"
                >
                  ×
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

// Tree Visualizer for the Solution
const PipelineTree = ({ node, isRoot = true }: { node: SynthesisNode, isRoot?: boolean }) => {
  return (
    <div className={`flex flex-col items-center ${isRoot ? '' : 'mt-4'}`}>
      <div className={`
        border rounded p-2 text-sm shadow-sm min-w-[120px] text-center
        ${node.func ? 'bg-indigo-50 border-indigo-200 text-indigo-900' : 'bg-emerald-50 border-emerald-200 text-emerald-900'}
      `}>
        <div className="font-bold mb-1">{node.type}</div>
        {node.func ? (
          <div className="text-xs text-indigo-600">
            <div className="flex items-center justify-center gap-1">
              <Settings size={10} />
              <span>{node.func.name}</span>
            </div>
            <div className="opacity-75 mt-1 text-[10px]">
              {node.func.impl.type}
            </div>
          </div>
        ) : (
          <div className="text-xs text-emerald-600 flex items-center justify-center gap-1">
            <Database size={10} />
            <span>Source Data</span>
          </div>
        )}
      </div>
      
      {node.inputs.length > 0 && (
        <>
          <div className="h-4 w-px bg-slate-400"></div>
          <div className="flex gap-4 border-t border-slate-400 pt-0 relative">
             {node.inputs.map((child, idx) => (
               <div key={idx} className="relative pt-4">
                 <PipelineTree node={child} isRoot={false} />
               </div>
             ))}
          </div>
        </>
      )}
    </div>
  );
};

// --- Main App Component ---

export default function OntologySynthesisDemo() {
  const [selectedExample, setSelectedExample] = useState(DEFAULT_EXAMPLE);
  const [dsl, setDsl] = useState(DEFAULT_DSL);
  const [inputDataJson, setInputDataJson] = useState(DEFAULT_INPUT_DATA);
  const [catalog, setCatalog] = useState<Catalog>({ types: {}, funcs: [] });
  const [sourceType, setSourceType] = useState<string>(EXAMPLES[DEFAULT_EXAMPLE].source);
  const [targetType, setTargetType] = useState<string>(EXAMPLES[DEFAULT_EXAMPLE].target);
  const [solutions, setSolutions] = useState<SynthesisNode[]>([]);
  const [selectedSolutionIdx, setSelectedSolutionIdx] = useState<number | null>(null);
  const [executionResult, setExecutionResult] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'graph' | 'pipeline'>('pipeline');
  const [editMode, setEditMode] = useState<'text' | 'blocks'>('text');
  const [helpTopic, setHelpTopic] = useState<'dsl' | 'synthesis' | 'execution' | 'blocks' | null>(null);

  // Handle example selection
  const handleExampleChange = (exampleName: string) => {
    setSelectedExample(exampleName);
    const example = EXAMPLES[exampleName];
    setDsl(example.dsl);
    setInputDataJson(JSON.stringify(example.inputData, null, 2));
    setSourceType(example.source);
    setTargetType(example.target);
    setSolutions([]);
    setSelectedSolutionIdx(null);
    setExecutionResult(null);
  };

  // Generate DSL text from types and funcs
  const generateDSL = (types: TypeDef[], funcs: FuncDef[]): string => {
    const lines: string[] = [];

    // Generate type definitions
    types.forEach(type => {
      if (type.isProduct) {
        lines.push(`type ${type.name} = ${type.components.join(' x ')}`);
      } else {
        const attrs = Object.entries(type.attrs).map(([k, v]) => `${k}=${v}`).join(', ');
        lines.push(`type ${type.name}${attrs ? ` [${attrs}]` : ''}`);
      }
    });

    lines.push(''); // Empty line between types and functions

    // Generate function definitions
    funcs.forEach(func => {
      lines.push(`fn ${func.name} {`);
      lines.push(`  sig: ${func.dom.join(', ')} -> ${func.cod}`);
      lines.push(`  impl: ${func.impl.type}("${func.impl.value}")`);
      lines.push(`  cost: ${func.cost}`);
      lines.push(`  confidence: ${func.confidence}`);
      if (func.doc) {
        lines.push(`  doc: "${func.doc}"`);
      }
      lines.push(`}`);
      lines.push('');
    });

    return lines.join('\n');
  };

  // Handle block updates
  const handleBlockUpdate = (types: TypeDef[], funcs: FuncDef[]) => {
    const newDsl = generateDSL(types, funcs);
    setDsl(newDsl);
  };

  // Load DSL on change
  useEffect(() => {
    const parsed = parseDSL(dsl);
    setCatalog(parsed);
    
    // Set defaults if empty
    const typeNames = Object.keys(parsed.types);
    if (typeNames.length > 0) {
      if (!sourceType) setSourceType(typeNames[0]);
      if (!targetType) setTargetType(typeNames[typeNames.length - 1]);
    }
  }, [dsl]);

  const handleSolve = () => {
    // For demo, we treat single source selection as "available sources contains this type"
    // In reality, it might be a list of available source types.
    // Let's assume the user selects the "Leaf" of the tree they want to build from, 
    // or we assume all Types not produced by functions are sources.
    
    // Better strategy for this demo: User selects GOAL. System finds path from ANY primitives.
    // The "SourceType" selector in UI will just be for specific constraint testing if needed,
    // but let's just use "Facility" as the implicit source for the default scenario.
    
    const sols = solveInhabitation(targetType, [sourceType], catalog);
    setSolutions(sols);
    setSelectedSolutionIdx(sols.length > 0 ? 0 : null);
    setExecutionResult(null);
    setActiveTab('pipeline');
  };

  const handleExecute = () => {
    if (selectedSolutionIdx === null) return;
    try {
      const context = JSON.parse(inputDataJson);
      const res = executePipeline(solutions[selectedSolutionIdx], context);
      setExecutionResult(JSON.stringify(res));
    } catch (e) {
      setExecutionResult("Error: Invalid JSON Input or Logic");
    }
  };

  const typeOptions = Object.keys(catalog.types);

  return (
    <>
      <HelpModal
        isOpen={helpTopic !== null}
        onClose={() => setHelpTopic(null)}
        topic={helpTopic || 'dsl'}
      />
      <div className="flex h-screen bg-slate-50 text-slate-800 font-sans overflow-hidden">
      
      {/* Left Panel: DSL & Config */}
      <div className="w-1/3 flex flex-col border-r border-slate-200">
        <div className="p-4 border-b border-slate-200 bg-white">
          <h1 className="text-lg font-bold flex items-center gap-2 text-blue-600">
            <Layers className="w-5 h-5" />
            Ontology Synthesizer
          </h1>
          <p className="text-xs text-slate-500 mt-1">型理論に基づく合成シミュレータ</p>
        </div>

        {/* Example Selector */}
        <div className="p-4 bg-slate-50 border-b border-slate-200">
          <label className="block text-xs font-bold text-slate-600 mb-2">事例選択 (Examples)</label>
          <select
            className="w-full bg-white border border-slate-300 rounded p-2 text-sm focus:border-blue-500 outline-none text-slate-700 font-medium"
            value={selectedExample}
            onChange={(e) => handleExampleChange(e.target.value)}
          >
            {Object.keys(EXAMPLES).map((exampleName) => (
              <option key={exampleName} value={exampleName}>
                {exampleName}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 flex flex-col min-h-0">
          {/* Mode Toggle */}
          <div className="bg-slate-100 text-xs px-4 py-2 font-bold text-slate-600 flex justify-between items-center border-b border-slate-200">
            <div className="flex items-center gap-2">
              <span>DSL DEFINITION</span>
              <button
                onClick={() => setHelpTopic(editMode === 'text' ? 'dsl' : 'blocks')}
                className="text-blue-500 hover:text-blue-700"
                title="ヘルプを表示"
              >
                <HelpCircle size={14} />
              </button>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setEditMode('blocks')}
                className={`px-2 py-1 rounded flex items-center gap-1 ${editMode === 'blocks' ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 hover:bg-slate-200'}`}
                title="Block Editor"
              >
                <Box size={12} />
                Blocks
              </button>
              <button
                onClick={() => setEditMode('text')}
                className={`px-2 py-1 rounded flex items-center gap-1 ${editMode === 'text' ? 'bg-blue-500 text-white' : 'bg-white text-slate-600 hover:bg-slate-200'}`}
                title="Text Editor"
              >
                <FileText size={12} />
                Text
              </button>
            </div>
          </div>

          {/* Editor Content */}
          {editMode === 'text' ? (
            <textarea
              className="flex-1 bg-white p-4 font-mono text-sm resize-none focus:outline-none focus:ring-1 ring-blue-500 text-slate-800 leading-relaxed"
              value={dsl}
              onChange={(e) => setDsl(e.target.value)}
              spellCheck={false}
            />
          ) : (
            <BlockEditor
              types={Object.values(catalog.types)}
              funcs={catalog.funcs}
              onUpdate={handleBlockUpdate}
            />
          )}
        </div>

        <div className="p-4 border-t border-slate-200 bg-white space-y-4 shadow-sm z-10">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">SOURCE TYPE (Start)</label>
              <select 
                className="w-full bg-white border border-slate-300 rounded p-2 text-sm focus:border-blue-500 outline-none text-slate-700"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
                {typeOptions.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">GOAL TYPE (Target)</label>
              <select 
                className="w-full bg-white border border-slate-300 rounded p-2 text-sm focus:border-blue-500 outline-none text-slate-700"
                value={targetType}
                onChange={(e) => setTargetType(e.target.value)}
              >
                {typeOptions.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSolve}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded flex items-center justify-center gap-2 font-bold transition-colors shadow-sm"
            >
              <Zap size={16} />
              パス探索 (Synthesize)
            </button>
            <button
              onClick={() => setHelpTopic('synthesis')}
              className="bg-white border border-blue-600 text-blue-600 hover:bg-blue-50 p-2 rounded"
              title="パス探索のヘルプ"
            >
              <HelpCircle size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel: Visualization & Execution */}
      <div className="flex-1 flex flex-col bg-slate-100">
        
        {/* Tabs */}
        <div className="flex border-b border-slate-200 bg-white shadow-sm z-10">
          <button 
            onClick={() => setActiveTab('pipeline')}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'pipeline' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          >
            <TrendingUp size={16} />
            合成パス & 実行
          </button>
          <button 
            onClick={() => setActiveTab('graph')}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'graph' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          >
            <Activity size={16} />
            カタロググラフ (Catalog)
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 p-6 overflow-auto">
          {activeTab === 'graph' ? (
            <div className="h-full flex flex-col">
              <div className="mb-4 text-sm text-slate-600 font-bold">定義された型と関数の関係図</div>
              <div className="flex-1">
                <GraphVisualizer catalog={catalog} />
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col">
              {solutions.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 rounded-lg bg-white/50">
                  <Box size={48} className="mb-4 opacity-50" />
                  <p>パスが見つかりません。探索を実行してください。</p>
                  <p className="text-xs mt-2 text-slate-500">※ ソースとゴールが適切に接続されているか確認してください。</p>
                </div>
              ) : (
                <div className="flex flex-col h-full gap-6">
                  {/* Solution Selector */}
                  <div className="flex gap-4 overflow-x-auto pb-2">
                    {solutions.map((sol, idx) => (
                      <div 
                        key={idx}
                        onClick={() => {
                          setSelectedSolutionIdx(idx);
                          setExecutionResult(null);
                        }}
                        className={`cursor-pointer min-w-[200px] p-3 rounded border shadow-sm transition-all ${selectedSolutionIdx === idx ? 'bg-blue-50 border-blue-400 ring-1 ring-blue-400' : 'bg-white border-slate-200 hover:border-slate-300'}`}
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className={`text-xs font-bold ${selectedSolutionIdx === idx ? 'text-blue-800' : 'text-slate-700'}`}>Path #{idx + 1}</span>
                          {idx === 0 && <span className="text-[10px] bg-green-100 text-green-700 border border-green-200 px-1 rounded">Best</span>}
                        </div>
                        <div className="space-y-1 text-xs text-slate-500">
                          <div className="flex justify-between">
                            <span>Cost:</span>
                            <span className="text-slate-800 font-medium">{sol.accumulatedCost.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Conf:</span>
                            <span className="text-slate-800 font-medium">{(sol.accumulatedConfidence * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Pipeline Visualizer */}
                  <div className="flex-1 bg-white/70 rounded-lg border border-slate-200 p-6 flex justify-center overflow-auto items-start shadow-sm">
                    {selectedSolutionIdx !== null && (
                      <PipelineTree node={solutions[selectedSolutionIdx]} />
                    )}
                  </div>

                  {/* Execution Area */}
                  <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-sm">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
                        <Database size={16} />
                        実行データ入力 (Input Context JSON)
                      </div>
                      <button
                        onClick={() => setHelpTopic('execution')}
                        className="text-blue-500 hover:text-blue-700"
                        title="実行と結果のヘルプ"
                      >
                        <HelpCircle size={16} />
                      </button>
                    </div>
                    <div className="flex gap-4 h-32">
                      <textarea 
                        className="flex-1 bg-slate-50 p-3 rounded font-mono text-xs text-slate-800 resize-none border border-slate-300 focus:border-blue-500 outline-none"
                        value={inputDataJson}
                        onChange={(e) => setInputDataJson(e.target.value)}
                      />
                      <div className="w-1/3 flex flex-col gap-2">
                        <button 
                          onClick={handleExecute}
                          className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold flex flex-col items-center justify-center gap-2 transition-colors shadow-sm"
                        >
                          <Play size={24} />
                          <span>実行 (Execute)</span>
                        </button>
                      </div>
                    </div>
                    {executionResult && (
                      <div className="mt-4 p-3 bg-slate-50 border border-emerald-200 rounded flex items-center justify-between">
                         <span className="text-slate-500 text-xs font-bold uppercase">Result</span>
                         <span className="text-emerald-600 font-mono text-lg font-bold">{executionResult}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}