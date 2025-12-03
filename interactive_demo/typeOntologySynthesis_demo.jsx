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
  Box
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

// --- Default DSL ---

const DEFAULT_DSL = `# GHG排出量計算オントロジー例

# --- 型定義 (Type) ---
type Facility
  attr unit:string
  attr id:string

type PowerUsage
  attr unit:kWh

type EmissionFactor
  attr unit:kg-CO2/kWh

type TotalGHG
  attr unit:kg-CO2

# --- 関数定義 (Fn) ---

# 施設のIDから電力使用量を取得 (Mock DB/API)
fn lookupUsage(Facility) -> PowerUsage
  cost 1.0
  conf 0.9
  impl rest:GET /api/usage/{id}
  doc 施設IDに基づいて電力消費量を取得

# 地域ごとの排出係数を取得
fn lookupFactor(Facility) -> EmissionFactor
  cost 0.5
  conf 0.95
  impl sparql:SELECT ?factor WHERE { ?f hasRegion ?r . ?r hasFactor ?factor }
  doc 施設の地域係数をDBから取得

# 排出量を計算 (使用量 x 係数)
fn calcEmission(PowerUsage, EmissionFactor) -> TotalGHG
  cost 0.1
  conf 1.0
  impl formula:arg0 * arg1
  doc 電力使用量と係数を掛け合わせる
`;

const DEFAULT_INPUT_DATA = JSON.stringify({
  "Facility": { "id": "factory_01", "region": "JP-East" },
  "lookupUsage": 1200,    // Mock result for demo
  "lookupFactor": 0.45    // Mock result for demo
}, null, 2);

// --- Parser Logic (Phase 1) ---

const parseDSL = (text: string): Catalog => {
  const types: Record<string, TypeDef> = {};
  const funcs: FuncDef[] = [];
  
  const lines = text.split('\n');
  let currentBlock: 'none' | 'type' | 'fn' = 'none';
  let currentObj: any = null;

  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith('#')) continue;

    if (line.startsWith('type ')) {
      currentBlock = 'type';
      const parts = line.substring(5).trim().split(' ');
      const name = parts[0];
      // Check for Product Type (Not fully implemented in parser logic for simplicity but structure exists)
      const isProduct = name.includes(' x '); 
      
      currentObj = {
        name: name,
        attrs: {},
        isProduct: false,
        components: []
      };
      types[name] = currentObj;
    } else if (line.startsWith('fn ')) {
      currentBlock = 'fn';
      // Format: fn name(A, B) -> C
      const match = line.match(/fn\s+(\w+)\s*\((.*?)\)\s*->\s*(\w+)/);
      if (match) {
        currentObj = {
          name: match[1],
          dom: match[2].split(',').map(s => s.trim()).filter(s => s),
          cod: match[3].trim(),
          cost: 0,
          confidence: 1.0,
          impl: { type: 'builtin', value: '' }
        };
        funcs.push(currentObj);
      }
    } else if (currentBlock === 'type' && line.startsWith('attr ')) {
      const parts = line.substring(5).split(':');
      if (parts.length === 2 && currentObj) {
        currentObj.attrs[parts[0].trim()] = parts[1].trim();
      }
    } else if (currentBlock === 'fn' && currentObj) {
      if (line.startsWith('cost ')) currentObj.cost = parseFloat(line.substring(5));
      else if (line.startsWith('conf ')) currentObj.confidence = parseFloat(line.substring(5));
      else if (line.startsWith('doc ')) currentObj.doc = line.substring(4);
      else if (line.startsWith('impl ')) {
        const parts = line.substring(5).split(':');
        currentObj.impl = {
          type: parts[0].trim(),
          value: parts.slice(1).join(':').trim()
        };
      }
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
      // Very basic formula parser for demo (arg0 + arg1 etc)
      // Safety: In a real app, do not use Function/eval loosely.
      try {
        const formula = f.impl.value
          .replace(/arg(\d+)/g, (_, idx) => JSON.stringify(inputValues[parseInt(idx)]));
        // eslint-disable-next-line no-new-func
        return new Function(`return ${formula}`)();
      } catch (e) {
        return `Error evaluating ${formula}`;
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

const GraphVisualizer = ({ catalog }: { catalog: Catalog }) => {
  // Simple layouting for demo purposes
  // Group types by whether they are sources (no incoming edges in pure directed graph context is hard to guess without full graph analysis, 
  // so we just place them randomly or in a circle)
  
  return (
    <div className="relative w-full h-full bg-white overflow-hidden border border-slate-200 rounded-lg flex items-center justify-center p-4 shadow-sm">
      <div className="text-slate-400 absolute top-2 right-2 text-xs">簡易グラフビュー</div>
      {/* SVG Rendering of nodes and edges */}
      <svg className="w-full h-full" viewBox="0 0 600 400">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#64748b" />
          </marker>
        </defs>
        
        {/* Render Logic: Simplified Force Layout or Layered Layout simulation */}
        {/* Since implementing a full force-layout in a single file React component is heavy, 
            we will render a static conceptual representation based on the loaded DSL */}
        
        {Object.keys(catalog.types).map((typeName, i) => {
          const x = 50 + (i * 150) % 500;
          const y = 50 + Math.floor(i / 3) * 100;
          return (
            <g key={typeName}>
              <circle cx={x} cy={y} r="30" fill="#f1f5f9" stroke="#3b82f6" strokeWidth="2" />
              <text x={x} y={y} dy="5" textAnchor="middle" fill="#1e293b" fontSize="10" className="pointer-events-none font-bold">
                {typeName.substring(0, 8)}
              </text>
            </g>
          );
        })}
        
        {catalog.funcs.map((f, i) => {
           // Find coords (very rough for demo)
           const startType = f.dom[0];
           const endType = f.cod;
           const startIdx = Object.keys(catalog.types).indexOf(startType);
           const endIdx = Object.keys(catalog.types).indexOf(endType);
           
           if (startIdx === -1 || endIdx === -1) return null;

           const sx = 50 + (startIdx * 150) % 500;
           const sy = 50 + Math.floor(startIdx / 3) * 100;
           const ex = 50 + (endIdx * 150) % 500;
           const ey = 50 + Math.floor(endIdx / 3) * 100;

           return (
             <g key={i}>
                <line x1={sx} y1={sy} x2={ex} y2={ey} stroke="#94a3b8" strokeWidth="1" markerEnd="url(#arrowhead)" />
                <text x={(sx+ex)/2} y={(sy+ey)/2} fill="#64748b" fontSize="8" dy="-5">{f.name}</text>
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
  const [dsl, setDsl] = useState(DEFAULT_DSL);
  const [inputDataJson, setInputDataJson] = useState(DEFAULT_INPUT_DATA);
  const [catalog, setCatalog] = useState<Catalog>({ types: {}, funcs: [] });
  const [sourceType, setSourceType] = useState<string>('');
  const [targetType, setTargetType] = useState<string>('');
  const [solutions, setSolutions] = useState<SynthesisNode[]>([]);
  const [selectedSolutionIdx, setSelectedSolutionIdx] = useState<number | null>(null);
  const [executionResult, setExecutionResult] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'graph' | 'pipeline'>('pipeline');

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

        <div className="flex-1 flex flex-col min-h-0">
          <div className="bg-slate-100 text-xs px-4 py-2 font-bold text-slate-600 flex justify-between items-center border-b border-slate-200">
            <span>DSL DEFINITION</span>
            <Code size={14} />
          </div>
          <textarea
            className="flex-1 bg-white p-4 font-mono text-sm resize-none focus:outline-none focus:ring-1 ring-blue-500 text-slate-800 leading-relaxed"
            value={dsl}
            onChange={(e) => setDsl(e.target.value)}
            spellCheck={false}
          />
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

          <button
            onClick={handleSolve}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded flex items-center justify-center gap-2 font-bold transition-colors shadow-sm"
          >
            <Zap size={16} />
            パス探索 (Synthesize)
          </button>
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
                    <div className="flex items-center gap-2 mb-3 text-sm font-bold text-slate-700">
                      <Database size={16} />
                      実行データ入力 (Input Context JSON)
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
  );
}