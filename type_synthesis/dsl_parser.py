"""
DSLパーサー

DSL構文:
- type <型名> [<属性リスト>]
- type <型名> = <型1> x <型2> x ...  (Product型)
- fn <関数名> { sig: ..., impl: ..., cost: ..., ... }
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from synth_lib import Catalog, TypeDef, ProductType, Func


class DSLParseError(Exception):
    """DSLパースエラー"""
    def __init__(self, message: str, line_num: int = None, line_content: str = None):
        self.line_num = line_num
        self.line_content = line_content
        super().__init__(self._format_message(message))
    
    def _format_message(self, message: str) -> str:
        if self.line_num is not None:
            return f"Line {self.line_num}: {message}"
        return message


class DSLParser:
    """DSLパーサー"""
    
    def __init__(self):
        self.catalog = Catalog()
        self._line_num = 0
        self._current_line = ""
    
    def parse(self, dsl_text: str) -> Catalog:
        """DSLテキストをパースしてCatalogを返す"""
        lines = dsl_text.split('\n')
        i = 0
        
        while i < len(lines):
            self._line_num = i + 1
            line = lines[i].strip()
            self._current_line = line
            
            # 空行・コメント行をスキップ
            if not line or line.startswith('#'):
                i += 1
                continue
            
            # 行末コメントを除去
            if '#' in line:
                line = line[:line.index('#')].strip()
            
            # type定義
            if line.startswith('type '):
                self._parse_type(line)
                i += 1
            
            # fn定義
            elif line.startswith('fn '):
                func_lines, consumed = self._collect_block(lines, i)
                self._parse_func(func_lines)
                i += consumed
            
            else:
                raise DSLParseError(f"Unknown syntax: {line}", self._line_num, line)
        
        return self.catalog
    
    def _parse_type(self, line: str):
        """型定義をパース"""
        # type <型名> = <型1> x <型2> x ...  (Product型)
        product_match = re.match(r'type\s+(\w+)\s*=\s*(.+)', line)
        if product_match:
            name = product_match.group(1)
            components_str = product_match.group(2)
            # 'x' または '×' で分割
            components = [c.strip() for c in re.split(r'\s*[x×]\s*', components_str)]
            product_type = ProductType(name=name, components=components)
            self.catalog.add_product_type(product_type)
            return
        
        # type <型名> [<属性リスト>]
        type_match = re.match(r'type\s+(\w+)(?:\s*\[([^\]]*)\])?', line)
        if type_match:
            name = type_match.group(1)
            attrs_str = type_match.group(2)
            attrs = self._parse_attrs(attrs_str) if attrs_str else {}
            type_def = TypeDef(name=name, attrs=attrs)
            self.catalog.add_type(type_def)
            return
        
        raise DSLParseError(f"Invalid type definition: {line}", self._line_num)
    
    def _parse_attrs(self, attrs_str: str) -> Dict[str, str]:
        """属性リストをパース: unit=J, range=>=0"""
        attrs = {}
        if not attrs_str:
            return attrs
        
        for pair in attrs_str.split(','):
            pair = pair.strip()
            if '=' in pair:
                key, value = pair.split('=', 1)
                attrs[key.strip()] = value.strip()
        
        return attrs
    
    def _collect_block(self, lines: List[str], start: int) -> Tuple[str, int]:
        """
        ブロック（{...}）を収集
        
        Returns:
            (ブロック全体の文字列, 消費した行数)
        """
        block_lines = []
        brace_count = 0
        started = False
        i = start
        
        while i < len(lines):
            line = lines[i]
            # コメントを除去（文字列リテラル内のコメントは考慮しない簡易実装）
            clean_line = line
            if '#' in clean_line and '"' not in clean_line:
                clean_line = clean_line[:clean_line.index('#')]
            
            block_lines.append(clean_line)
            
            for char in clean_line:
                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
            
            i += 1
            
            if started and brace_count == 0:
                break
        
        if brace_count != 0:
            raise DSLParseError("Unmatched braces in block", start + 1)
        
        return '\n'.join(block_lines), i - start
    
    def _parse_func(self, func_text: str):
        """関数定義をパース"""
        # fn <関数名> { ... }
        match = re.match(r'fn\s+(\w+)\s*\{(.*)\}', func_text, re.DOTALL)
        if not match:
            raise DSLParseError(f"Invalid function definition", self._line_num)
        
        name = match.group(1)
        body = match.group(2)
        
        # 各フィールドをパース
        fields = self._parse_func_body(body)
        
        # シグネチャをパース
        if 'sig' not in fields:
            raise DSLParseError(f"Function '{name}' missing 'sig' field", self._line_num)
        
        dom, cod = self._parse_signature(fields['sig'])
        
        # implをパース
        impl = self._parse_impl(fields.get('impl', 'builtin("identity")'))
        
        # 関数を作成
        func = Func(
            id=name,
            dom=dom,
            cod=cod,
            cost=float(fields.get('cost', 1.0)),
            conf=float(fields.get('confidence', 1.0)),
            impl=impl,
            inverse_of=fields.get('inverse_of'),
            doc=fields.get('doc', '').strip('"')
        )
        
        self.catalog.add_func(func)
    
    def _parse_func_body(self, body: str) -> Dict[str, str]:
        """関数ボディをパース: key: value 形式"""
        fields = {}
        
        # 各行を処理
        for line in body.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # key: value 形式
            match = re.match(r'(\w+)\s*:\s*(.+)', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                fields[key] = value
        
        return fields
    
    def _parse_signature(self, sig_str: str) -> Tuple[Any, str]:
        """
        シグネチャをパース
        
        単一: A -> B
        多引数: (A, B, C) -> D
        
        Returns:
            (dom, cod) - domは文字列またはリスト
        """
        sig_str = sig_str.strip()
        
        # -> で分割
        parts = sig_str.split('->')
        if len(parts) != 2:
            raise DSLParseError(f"Invalid signature: {sig_str}", self._line_num)
        
        dom_str = parts[0].strip()
        cod = parts[1].strip()
        
        # 多引数: (A, B, C)
        if dom_str.startswith('(') and dom_str.endswith(')'):
            inner = dom_str[1:-1]
            dom = [t.strip() for t in inner.split(',')]
        else:
            dom = dom_str
        
        return dom, cod
    
    def _parse_impl(self, impl_str: str) -> Dict[str, Any]:
        """
        実装仕様をパース

        - sparql("...")
        - formula("...")
        - rest("...")
        - builtin("...")
        - json({...})
        - template("...", {...})
        """
        impl_str = impl_str.strip()

        # sparql("...")
        match = re.match(r'sparql\s*\(\s*"([^"]*)"\s*\)', impl_str)
        if match:
            return {"type": "sparql", "query": match.group(1)}

        # formula("...")
        match = re.match(r'formula\s*\(\s*"([^"]*)"\s*\)', impl_str)
        if match:
            return {"type": "formula", "expr": match.group(1)}

        # rest("...")
        match = re.match(r'rest\s*\(\s*"([^"]*)"\s*\)', impl_str)
        if match:
            content = match.group(1)
            # "METHOD, URL" 形式
            if ',' in content:
                method, url = content.split(',', 1)
                return {"type": "rest", "method": method.strip(), "url": url.strip()}
            return {"type": "rest", "url": content}

        # builtin("...")
        match = re.match(r'builtin\s*\(\s*"([^"]*)"\s*\)', impl_str)
        if match:
            return {"type": "builtin", "name": match.group(1)}

        # json({...})
        if impl_str.startswith('json'):
            schema_match = re.match(r'json\s*\(\s*(\{.*\})\s*\)', impl_str, re.DOTALL)
            if schema_match:
                import json
                try:
                    schema = json.loads(schema_match.group(1))
                    return {"type": "json", "schema": schema}
                except json.JSONDecodeError as e:
                    raise DSLParseError(f"Invalid JSON schema: {e}")

        # template("template_str", {mappings})
        if impl_str.startswith('template'):
            template_match = re.match(r'template\s*\(\s*"([^"]+)"\s*,\s*(\{.*\})\s*\)', impl_str, re.DOTALL)
            if template_match:
                import json
                template_str = template_match.group(1)
                try:
                    mappings = json.loads(template_match.group(2))
                    return {"type": "template", "template": template_str, "mappings": mappings}
                except json.JSONDecodeError as e:
                    raise DSLParseError(f"Invalid template mappings: {e}")

        # デフォルトはidentity
        return {"type": "builtin", "name": "identity"}


def parse_dsl(dsl_text: str) -> Catalog:
    """DSLテキストをパースしてCatalogを返す"""
    parser = DSLParser()
    return parser.parse(dsl_text)


def parse_dsl_file(file_path: str) -> Catalog:
    """DSLファイルをパースしてCatalogを返す"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return parse_dsl(f.read())


if __name__ == "__main__":
    # テスト
    test_dsl = '''
# 型定義
type Product
type Energy [unit=J, range=>=0]
type Fuel [unit=kg]
type CO2 [unit=kg]

# Product型
type AllScopesEmissions = Scope1Emissions x Scope2Emissions x Scope3Emissions

# 関数定義
fn usesEnergy {
  sig: Product -> Energy
  impl: sparql("SELECT ?p ?e WHERE { ?p :usesEnergy ?e }")
  cost: 1
  confidence: 0.9
}

fn fuelToCO2 {
  sig: Fuel -> CO2
  impl: formula("co2 = fuel_amount * emission_factor")
  cost: 1
  confidence: 0.98
}

fn energyToFuelEstimate {
  sig: Energy -> Fuel
  impl: formula("fuel = energy / efficiency")
  cost: 3
  confidence: 0.8
  inverse_of: fuelToEnergy
}

fn aggregateScopes {
  sig: (Scope1Emissions, Scope2Emissions, Scope3Emissions) -> TotalGHGEmissions
  impl: formula("total = scope1 + scope2 + scope3")
  cost: 1
  confidence: 1.0
}
'''
    
    catalog = parse_dsl(test_dsl)
    
    print("Types:")
    for name, t in catalog.types.items():
        print(f"  {name}: {t.attrs}")
    
    print("\nProduct Types:")
    for name, pt in catalog.product_types.items():
        print(f"  {name} = {' x '.join(pt.components)}")
    
    print("\nFunctions:")
    for f in catalog.funcs:
        print(f"  {f.id}: {f.signature}")
        print(f"    cost={f.cost}, conf={f.conf}, impl={f.impl}")
