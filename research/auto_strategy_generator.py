# auto_strategy_generator.py
"""
Auto-generate multiple strategy plugins by grid-search or random sampling
using a Jinja2 template and writing out .py modules.

Usage:
    python auto_strategy_generator.py \
        --template research/templates/strategy_template.j2 \
        --output-dir strategy \
        --mode grid \
        --grid ema_period=50,100,150 threshold=0.005,0.01,0.02 \
        [--count N]  # for random sampling
"""
import argparse
import itertools
import json
import random
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


def parse_grid(grid_args):
    grid = {}
    for item in grid_args:
        key, vals = item.split('=')
        grid[key] = [float(v) if '.' in v else int(v) for v in vals.split(',')]
    return grid


def main():
    parser = argparse.ArgumentParser(description="Auto-generate strategy modules from template.")
    parser.add_argument("--template", required=True, help="Path to Jinja2 template (.j2)")
    parser.add_argument("--output-dir", default="strategy", help="Directory to write .py files")
    parser.add_argument("--mode", choices=["grid", "random"], default="grid",
                        help="Generation mode: grid or random sampling")
    parser.add_argument(
        "--grid",
        nargs="+",
        help="Grid definitions like ema_period=50,100 threshold=0.01,0.02",
    )
    parser.add_argument("--params", help="JSON file with base params to extend (for random mode)")
    parser.add_argument("--count", type=int, default=10,
                        help="Number of random strategies to generate (random mode)")
    args = parser.parse_args()

    tpl_path = Path(args.template)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(tpl_path.parent)),
                      trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(tpl_path.name)

    if args.mode == "grid":
        grid = parse_grid(args.grid)
        keys, values = zip(*grid.items())
        for combo in itertools.product(*values):
            ctx = {
                "strategy_name": (
                    f"Auto_{'_'.join(str(int(v) if isinstance(v, float) and v.is_integer() else str(v)) "
                    f"for v in combo)}"
                ),
                "description": "Grid-generated strategy",
                "default_ema": combo[keys.index('ema_period')] if 'ema_period' in keys else 50,
                "params": []
            }
            # build params list
            for key, val in zip(keys, combo):
                ctx['params'].append({"name": key, "default": val, "doc": f"Auto-generated {key}"})

            code = template.render(**ctx)
            fname = output_dir / f"{ctx['strategy_name'].lower()}.py"
            fname.write_text(code, encoding='utf-8')
            print(f"Generated {fname}")

    else:  # random mode
        base = {}
        if args.params:
            base = json.loads(Path(args.params).read_text())
        for i in range(args.count):
            params = []
            for k, v in base.items():
                if isinstance(v, (int, float)):
                    # randomize around base ±20%
                    delta = v * 0.2
                    val = round(random.uniform(v - delta, v + delta), 6)
                    params.append({"name": k, "default": val, "doc": f"Randomized {k}"})
            name = f"Rnd_{i}"
            ctx = {
                "strategy_name": name,
                "description": "Randomized strategy",
                "params": params,
                "default_ema": base.get('ema_period', 50),
            }
            code = template.render(**ctx)
            fname = output_dir / f"{ctx['strategy_name'].lower()}.py"
            fname.write_text(code, encoding='utf-8')
            print(f"Generated {fname}")

if __name__ == "__main__":
    main()


# This script auto-generates strategy plugins based on a Jinja2 template.
# It supports both grid-based generation and random sampling of parameters.