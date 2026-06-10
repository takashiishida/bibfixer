from __future__ import annotations

import sys
from typing import Dict, Any, Optional, Tuple
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from .agent import BibFixAgent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Revise BibTeX entries using LLM with web search"
    )
    parser.add_argument(
        "-i", "--input",
        dest="input_file",
        required=True,
        help="Path to input .bib file",
    )
    parser.add_argument(
        "-p", "--preferences", default="", help="User preferences for formatting"
    )
    parser.add_argument(
        "--prompt-file",
        dest="prompt_file",
        default=None,
        help="Path to instruction prompt (default: bundled prompts/default.md)",
    )
    parser.add_argument("-o", "--output", help="Output file (default: print to stdout)")
    parser.add_argument(
        "--api-key", help="API key (or set OPENAI_API_KEY / OPENROUTER_API_KEY env var)"
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "openrouter"],
        default="openai",
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model name",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=1,
        help="Number of parallel workers for processing entries (default: 1)",
    )

    args = parser.parse_args()

    if not args.input_file.lower().endswith(".bib"):
        print("Error: Input file must be a .bib file", file=sys.stderr)
        sys.exit(1)

    # Never let console encoding (e.g. cp1252 on Windows) crash a run when
    # printing entries that contain non-ASCII characters.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    try:
        # utf-8-sig also accepts a UTF-8 BOM, which Windows editors often add
        with open(args.input_file, "r", encoding="utf-8-sig") as f:
            bibtex_content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(
            f"Error reading file: not valid UTF-8 ({str(e)}). "
            "Please re-save the .bib file with UTF-8 encoding.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {str(e)}", file=sys.stderr)
        sys.exit(1)

    try:
        agent = BibFixAgent(api_key=args.api_key, prompt_file=args.prompt_file, provider=args.provider)
        if args.model:
            agent.model = args.model
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    try:
        db = bibtexparser.loads(bibtex_content)
        entries = db.entries or []
        if not entries:
            print("Error: No valid BibTeX entries found", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error parsing BibTeX: {str(e)}", file=sys.stderr)
        sys.exit(1)

    def _dump_single_entry(entry_dict: Dict[str, Any]) -> str:
        single_db = BibDatabase()
        single_db.entries = [entry_dict]
        writer = BibTexWriter()
        writer.order_entries_by = None
        return writer.write(single_db)

    num_workers = max(1, args.workers)
    n = len(entries)
    label = "sequentially" if num_workers == 1 else f"with {num_workers} workers"
    print(
        f"Found {n} entr{'y' if n==1 else 'ies'}; processing {label}...",
        file=sys.stderr,
    )

    def _process_entry(idx: int, entry: Dict[str, Any]) -> tuple[int, str, str, str | None]:
        """Return (idx, original_text, revised_text, error_msg)."""
        key = entry.get("ID", f"entry_{idx}")
        original_text = _dump_single_entry(entry)
        try:
            revised = agent.revise_bibtex(original_text, args.preferences)
            print(f"  Done {idx}/{n}: {key}", file=sys.stderr)
            return idx, original_text, revised.strip(), None
        except Exception as e:
            print(
                f"  Error revising entry '{key}': {str(e)} — keeping original",
                file=sys.stderr,
            )
            return idx, original_text, original_text.strip(), str(e)

    # Open the output file up front and write entries (in input order) as
    # soon as they complete, so a failure partway through never discards the
    # results of earlier (expensive) revisions.
    out_f = None
    if args.output:
        try:
            out_f = open(args.output, "w", encoding="utf-8")
        except Exception as e:
            print(f"Error opening output file: {str(e)}", file=sys.stderr)
            sys.exit(1)

    next_write = 0  # index into results of the next entry to write

    def _flush_completed_prefix() -> None:
        """Write all consecutive completed entries starting at next_write."""
        nonlocal next_write
        while next_write < n and results[next_write] is not None:
            try:
                if next_write > 0:
                    out_f.write("\n")
                out_f.write(results[next_write][2] + "\n")
                out_f.flush()
            except Exception as e:
                print(f"Error writing output: {str(e)}", file=sys.stderr)
                sys.exit(1)
            next_write += 1

    # Process entries (parallel or sequential depending on num_workers)
    results: list[tuple[int, str, str, str | None]] = [None] * n  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(_process_entry, idx, entry): idx
            for idx, entry in enumerate(entries, start=1)
        }
        for future in as_completed(futures):
            idx, original_text, revised_text, err = future.result()
            results[idx - 1] = (idx, original_text, revised_text, err)
            if out_f:
                _flush_completed_prefix()

    # Print before/after in order
    separator = "=" * 80
    for idx, original_text, revised_text, err in results:
        print(separator)
        print("--- BEFORE ---")
        print(original_text.strip())
        print("--- AFTER ----")
        print(revised_text.strip())
        print(separator)

    if out_f:
        out_f.close()
        print(
            f"Revised {len(entries)} entries written to {args.output}",
            file=sys.stderr,
        )
    else:
        print(
            "No output file specified. Preview shown above; not writing output file.",
            file=sys.stderr,
        )


