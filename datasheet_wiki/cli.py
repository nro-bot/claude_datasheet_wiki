"""Command-line interface for datasheet-wiki."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import TIER_PRESETS, Config
from .utils import log


def _build(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    if not pdf.exists():
        log(f"ERROR: PDF not found: {pdf}")
        return 2
    out = Path(args.out) if args.out else Path("wiki") / pdf.stem

    overrides = {
        "backend": args.backend,
        "model": args.model,
        "dpi": args.dpi,
        "semantic": True if args.semantic else None,
        "render_images": False if args.no_images else None,
        "max_pages": args.max_pages,
        "resume": False if args.no_resume else None,
        "title": args.title,
        "ollama_host": args.ollama_host,
        "progress": False if args.quiet else None,
        "embed_model": args.embed_model,
        "svd_path": Path(args.svd) if args.svd else None,
        "llm_format": True if args.llm_format else (False if args.no_llm_format else None),
    }
    cfg = Config.from_tier(pdf, out, args.compute, **overrides)

    if cfg.is_api_backend:
        log("NOTE: the large tier sends section text to a cloud LLM API. For a "
            "fully local build use --compute small (no LLM) or --compute medium (Ollama).")

    from .pipeline import run

    run(cfg)
    print(f"\nOpen your wiki:  datasheet-wiki serve {out}\n", file=sys.stderr)
    return 0


def _serve(args: argparse.Namespace) -> int:
    import functools
    import http.server
    import signal

    directory = Path(args.dir)
    if not (directory / "index.html").exists():
        log(f"ERROR: no index.html in {directory} — build it first.")
        return 2
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))

    class Server(http.server.ThreadingHTTPServer):
        # SO_REUSEADDR so the port is immediately re-bindable after we stop
        # (no lingering TIME_WAIT); daemon threads so an in-flight request can
        # never block Ctrl+C from exiting.
        allow_reuse_address = True
        daemon_threads = True

    try:
        httpd = Server(("127.0.0.1", args.port), handler)
    except OSError as exc:
        log(f"ERROR: cannot bind 127.0.0.1:{args.port} ({exc}). "
            f"Is another server already using it? Try -p <other-port>.")
        return 2

    # Make SIGTERM behave like Ctrl+C (clean shutdown + port release).
    signal.signal(signal.SIGTERM, lambda *_: _raise_keyboard_interrupt())

    log(f"Serving {directory} at http://127.0.0.1:{args.port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("Stopping…")
    finally:
        httpd.shutdown()       # stop the serve loop
        httpd.server_close()   # close the listening socket, freeing the port
    log("Stopped; port freed.")
    return 0


def _raise_keyboard_interrupt():
    raise KeyboardInterrupt


def _info(args: argparse.Namespace) -> int:
    from .pdf.extract import PdfDocument

    doc = PdfDocument(Path(args.pdf))
    print(f"Title:    {doc.title}")
    print(f"Pages:    {doc.page_count}")
    outline = doc.outline()
    print(f"Outline:  {len(outline)} entries")
    for item in outline[: args.limit]:
        print(f"  {'  ' * (item.level - 1)}{item.title}  (p.{item.page + 1})")
    if len(outline) > args.limit:
        print(f"  … {len(outline) - args.limit} more (use --limit)")
    doc.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="datasheet-wiki",
        description="Turn a microcontroller datasheet PDF into a searchable, "
        "hyperlinked, self-hosted wiki.",
    )
    p.add_argument("--version", action="version", version=f"datasheet-wiki {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Build a wiki from a PDF.")
    b.add_argument("pdf", help="Path to the datasheet PDF.")
    b.add_argument("-o", "--out", help="Output directory (default: wiki/<pdf-name>).")
    b.add_argument(
        "-c", "--compute", choices=list(TIER_PRESETS), default="small",
        help="Compute tier. " + "  ".join(f"[{k}] {v.description}" for k, v in TIER_PRESETS.items()),
    )
    b.add_argument("--backend", choices=["none", "ollama", "anthropic"], help="Override the tier's enrichment backend.")
    b.add_argument("--model", help="LLM model id (ollama/anthropic backends).")
    b.add_argument("--dpi", type=int, help="Page render DPI (override tier default).")
    b.add_argument("--svd", help="CMSIS-SVD file: authoritative registers for the register map and device.h export.")
    b.add_argument("--semantic", action="store_true", help="Build a local embedding index (sentence-transformers; for the planned Q&A).")
    fmt = b.add_mutually_exclusive_group()
    fmt.add_argument("--llm-format", action="store_true",
                     help="Use the LLM to reflow each page into clean HTML with figures/tables as images (needs an LLM backend; on by default for medium/large).")
    fmt.add_argument("--no-llm-format", action="store_true",
                     help="Disable LLM page formatting even on the medium/large tier.")
    b.add_argument("--embed-model", help="sentence-transformers model for the embedding index.")
    b.add_argument("--no-images", action="store_true", help="Skip rendering page images (faster, smaller).")
    b.add_argument("--max-pages", type=int, default=0, help="Only process the first N pages (quick test).")
    b.add_argument("--no-resume", action="store_true", help="Ignore caches and rebuild everything.")
    b.add_argument("--title", help="Override the wiki title.")
    b.add_argument("--ollama-host", help="Ollama base URL (default http://localhost:11434).")
    b.add_argument("-q", "--quiet", action="store_true", help="Suppress progress bars.")
    b.set_defaults(func=_build)

    s = sub.add_parser("serve", help="Serve a built wiki locally.")
    s.add_argument("dir", help="The built wiki directory.")
    s.add_argument("-p", "--port", type=int, default=8000)
    s.set_defaults(func=_serve)

    i = sub.add_parser("info", help="Print a PDF's outline and page count.")
    i.add_argument("pdf")
    i.add_argument("--limit", type=int, default=60)
    i.set_defaults(func=_info)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
