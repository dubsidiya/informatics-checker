#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tests.test_grade import SOLUTIONS
out=ROOT/'data'/'solution_manifest.json'
out.write_text(json.dumps([{'id':pid,'source':src} for pid,src in sorted(SOLUTIONS.items())],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('wrote',len(SOLUTIONS),out)
