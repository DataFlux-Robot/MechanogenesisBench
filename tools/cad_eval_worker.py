#!/usr/bin/env python3
"""CAD eval subprocess worker v2: desk-aware (parametric instances have varied desks)."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from money_bench_v5 import real_cad_eval

job = json.loads(Path(sys.argv[1]).read_text())
desk = tuple(job.get('desk') or (420, 280))
res = real_cad_eval(job['text'], job['capital'], Path(job['folder']), desk=desk)
Path(sys.argv[2]).write_text(json.dumps(res, default=str))
