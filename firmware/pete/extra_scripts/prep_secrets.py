"""Copy ``include/secrets.h.example`` → ``include/secrets.h`` when missing (CI / fresh clone)."""

from pathlib import Path

Import("env")

project_dir = Path(env["PROJECT_DIR"])
dst = project_dir / "include" / "secrets.h"
src = project_dir / "include" / "secrets.h.example"
if dst.exists():
    pass
elif not src.is_file():
    raise FileNotFoundError(f"Missing {src}; cannot synthesize secrets.h")
else:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    print(f"prep_secrets: created {dst} from example (edit for your network / CA)")
