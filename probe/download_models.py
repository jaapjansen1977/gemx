"""Download the inspected official Body Motion release; verify published LFS hashes.

Run only during initial installation with network access. Inference is separate.
"""
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HOME", "/workspace/.cache/huggingface")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[2]
RELEASES = [
    ("GEM-X", "4fce057963671fd95cd4154297944397e7b5a9a0", "weights", [
        "body_s240000.ckpt", "vitpose.pth", "motion_native77_e774_s292175.ckpt",
        "motion_stats_raw.npz", "body_video_native77.yaml", "body_config.json", "LICENSE",
    ]),
    ("SOMA-X", "d281db2d01553f7230c56e764cec00fe27ef23f7", "assets/soma", [
        "SOMA_neutral.npz", "SOMA_template_rig.usda", "SOMA_procedural_transforms.json", "LICENSE",
    ]),
]


def main():
    manifest = []
    for name, revision, directory, files in RELEASES:
        info = HfApi().model_info("nvidia/" + name, revision=revision, files_metadata=True)
        assert info.sha == revision
        published = {item.rfilename: item for item in info.siblings}
        for filename in files:
            print("Downloading/verifying", name, filename, flush=True)
            target = hf_hub_download("nvidia/" + name, filename, revision=revision,
                                     local_dir=ROOT / "gemx-upstream" / directory)
            digest = hashlib.sha256()
            with open(target, "rb") as source:
                for block in iter(lambda: source.read(4194304), b""):
                    digest.update(block)
            item = published[filename]
            if item.lfs and digest.hexdigest() != item.lfs.sha256:
                raise RuntimeError("Published SHA256 mismatch: " + filename)
            if Path(target).stat().st_size != item.size:
                raise RuntimeError("Published file size mismatch: " + filename)
            manifest.append({"repository": "nvidia/" + name, "revision": revision,
                             "filename": filename, "sha256": digest.hexdigest(), "bytes": item.size})
            (ROOT / "gemx/reports/downloaded-models.json").write_text(json.dumps(manifest, indent=2))
            print("Verified", filename, flush=True)


if __name__ == "__main__":
    main()
