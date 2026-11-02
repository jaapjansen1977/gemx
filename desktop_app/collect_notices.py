"""Retain installed distribution notices alongside packaged native dependencies."""
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
records=[]
for distribution in importlib.metadata.distributions():
    name=distribution.metadata['Name']; found=[]
    for relative in distribution.files or []:
        if not any(word in relative.name.lower() for word in ('license','licence','copying','notice','copyright')):continue
        path=Path(distribution.locate_file(relative))
        if not path.is_file() or path.stat().st_size>5_000_000:continue
        # Preserve safe relative hierarchy without allowing paths to escape output.
        parts=[part for part in relative.parts if part not in ('.','..')]
        target=output/name/Path(*parts);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target);found.append(str(relative))
    records.append(dict(name=name,version=distribution.version,notices=found))
for filename in ['LICENSE.txt','LICENSE']:
    path=Path(sys.base_prefix)/filename
    if path.is_file():shutil.copyfile(path,output/('Python-'+filename))
(output/'packages.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
