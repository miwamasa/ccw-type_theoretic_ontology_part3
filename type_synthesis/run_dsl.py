#!/usr/bin/env python3
"""
DSL実行スクリプト

Usage:
    python run_dsl.py <dsl_file> <source_type> <goal_type> [--execute <input_value>]
    python run_dsl.py catalog.dsl Product CO2
    python run_dsl.py catalog.dsl Product CO2 --execute 1000
"""

import sys
import json
import argparse
from typing import Optional

from dsl_parser import parse_dsl_file, DSLParseError
from synth_lib import synthesize_backward, synthesize_multiarg, Catalog
from executor import execute_synthesis_result, ExecutionContext


def format_results(results, src_type: str, goal_type: str) -> dict:
    """結果をJSON形式でフォーマット"""
    return {
        "goal": f"{src_type}->{goal_type}",
        "plans": [r.to_dict() for r in results]
    }


def main():
    parser = argparse.ArgumentParser(description="DSL実行スクリプト")
    parser.add_argument("dsl_file", help="DSLファイルパス")
    parser.add_argument("source_type", help="ソース型")
    parser.add_argument("goal_type", help="ゴール型")
    parser.add_argument("--execute", "-e", type=float, help="入力値を指定して実行")
    parser.add_argument("--max-cost", "-c", type=float, default=100.0, help="最大コスト")
    parser.add_argument("--max-results", "-n", type=int, default=10, help="最大結果数")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細出力")
    
    args = parser.parse_args()
    
    try:
        # DSLファイルをパース
        if args.verbose:
            print(f"Parsing {args.dsl_file}...", file=sys.stderr)
        
        catalog = parse_dsl_file(args.dsl_file)
        
        if args.verbose:
            print(f"  Types: {len(catalog.types)}", file=sys.stderr)
            print(f"  Product Types: {len(catalog.product_types)}", file=sys.stderr)
            print(f"  Functions: {len(catalog.funcs)}", file=sys.stderr)
        
        # パス探索
        if args.verbose:
            print(f"\nSearching path: {args.source_type} -> {args.goal_type}...", file=sys.stderr)
        
        results = synthesize_backward(
            catalog, 
            args.source_type, 
            args.goal_type,
            max_cost=args.max_cost,
            max_results=args.max_results
        )
        
        if not results:
            print(f"No path found from {args.source_type} to {args.goal_type}", file=sys.stderr)
            sys.exit(1)
        
        # 結果を出力
        output = format_results(results, args.source_type, args.goal_type)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        
        # 実行オプション
        if args.execute is not None:
            print("\n" + "="*60, file=sys.stderr)
            print(f"Executing with input value: {args.execute}", file=sys.stderr)
            
            context = ExecutionContext()
            result_value = execute_synthesis_result(results[0], args.execute, context)
            
            print(f"Result: {result_value}", file=sys.stderr)
            print("="*60, file=sys.stderr)
    
    except DSLParseError as e:
        print(f"Parse Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"File not found: {args.dsl_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
