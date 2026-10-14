#!/usr/bin/env python3
"""Create a self-contained release ZIP from the public distribution files."""
from pathlib import Path
import tempfile
import uuid
import zipfile

root = Path(__file__).resolve().parent.parent
dist = root / "dist"
output = dist / "js-client/manabi-grammar-db-client.zip"
if dist.resolve() != dist or output.parent.resolve() != output.parent:
    raise ValueError("Unexpected client packaging target")
output.parent.mkdir(parents=True, exist_ok=True)
required = {"index.js", "package.json", "sqlite3.mjs", "sqlite3-node.mjs", "sqlite3.wasm", "README.md", "LICENSE"}
files = sorted(path for path in dist.iterdir() if path.is_file())
if not required.issubset({path.name for path in files}):
    raise ValueError("Incomplete SQLite client distribution")
work = Path(tempfile.mkdtemp(prefix="manabi-client-pack-"))
archive = work / output.name
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in files:
        if path.resolve() != path:
            raise ValueError("Unexpected distribution symlink")
        bundle.write(path, path.name)
if output.exists():
    if output.resolve() != output:
        raise ValueError("Unexpected ZIP target")
    trash = Path.home() / ".Trash"
    if trash.resolve() != trash:
        raise ValueError("Unexpected Trash target")
    trash.mkdir(exist_ok=True)
    output.rename(trash / ("manabi-client-" + str(uuid.uuid4()) + ".zip"))
archive.rename(output)
print(f"Packaged {output}")
