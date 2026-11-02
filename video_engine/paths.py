"""Non-secret local runtime profile shared by the desktop and browser apps."""
import json
import os
from pathlib import Path


def profile_path():
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))
    return base/'GEMX/engine.json'


def load_profile():
    try:
        value=json.loads(profile_path().read_text(encoding='utf-8'))
        if value.get('status')!='ready_for_video_test':return None
        if not all(Path(value[k]).is_file() for k in ('python','config')):return None
        if not Path(value['assets']).is_dir():return None
        return value
    except (OSError,ValueError,KeyError,TypeError):return None
