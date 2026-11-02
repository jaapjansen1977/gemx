"""Create a small code-only Windows setup ZIP; no models or third-party binaries."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];args.output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.output,'w',ZIP_DEFLATED) as archive:
        archive.write(root/'desktop_app/setup_engine_windows.ps1','GEMX-videomotor/setup_engine_windows.ps1')
        for path in sorted((root/'video_engine').iterdir()):
            if path.is_file() and path.suffix in ('.py','.json','.txt','.md'):
                archive.write(path,'GEMX-videomotor/video_engine/'+path.name)
    with ZipFile(args.output) as archive:
        if archive.testzip() is not None:raise RuntimeError('Installer-ZIP ongeldig')
    print(args.output)


if __name__=='__main__':main()
