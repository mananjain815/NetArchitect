"""CLI:  python -m app.cli list | analyze <profile|file.json> | export [--out DIR]"""
import argparse
import json
import sys
from pathlib import Path

from app.analysis import analyze
from app.models.schemas import NetworkRequest
from app.presets import PRESETS


def _load(arg: str) -> NetworkRequest:
    if arg in PRESETS:
        return NetworkRequest(**PRESETS[arg])
    return NetworkRequest(**json.loads(Path(arg).read_text()))


def export_all(out: Path) -> list[Path]:
    written = []
    for key, preset in PRESETS.items():
        res = analyze(NetworkRequest(**preset))
        d = out / key
        d.mkdir(parents=True, exist_ok=True)
        for fname, text in res["configs"]["devices"].items():
            (d / fname).write_text(text)
            written.append(d / fname)
        full = out / f"{key}_full_config.txt"
        full.write_text(res["configs"]["bundle"])
        (out / f"{key}_rationale.md").write_text(res["report"]["markdown"])
        cab = ["# Cabling plan (build this in Packet Tracer / GNS3)", "",
               "| Link | A | A port | B | B port | Subnet |", "|---|---|---|---|---|---|"]
        for c in res["configs"]["cabling"]:
            cab.append(f"| {c['link']} | {c['a']} | {c['if_a']} | {c['b']} | {c['if_b']} | {c['subnet']} |")
        (out / f"{key}_cabling.md").write_text("\n".join(cab) + "\n")
        written += [full]
    return written


def main(argv=None):
    p = argparse.ArgumentParser(prog="netarchitect")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    a = sub.add_parser("analyze"); a.add_argument("source"); a.add_argument("--json", action="store_true")
    e = sub.add_parser("export"); e.add_argument("--out", default="exports")
    args = p.parse_args(argv)
    try:
        if args.cmd == "list":
            for k, v in PRESETS.items():
                print(f"{k:12} {v['name']}")
        elif args.cmd == "analyze":
            res = analyze(_load(args.source))
            print(json.dumps(res, indent=2, default=str) if args.json else res["report"]["markdown"])
        else:
            for f in export_all(Path(args.out)):
                print("wrote", f)
    except ValueError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
