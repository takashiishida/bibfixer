import sys
from typing import Dict, Any
import argparse
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from .agent import BibFixAgent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Revise BibTeX entries using GPT with web search"
    )
    parser.add_argument(
        "-i",
        "--input",
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
        "--api-key",
        help="API key for the selected provider (or set corresponding env var)",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "openrouter"],
        default="openai",
        help="API provider to use (default: openai). Set OPENAI_API_KEY or OPENROUTER_API_KEY env var accordingly.",
    )

    args = parser.parse_args()

    if not args.input_file.lower().endswith(".bib"):
        print("Error: Input file must be a .bib file", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.input_file, "r") as f:
            bibtex_content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {str(e)}", file=sys.stderr)
        sys.exit(1)

    try:
        agent = BibFixAgent(
            api_key=args.api_key, prompt_file=args.prompt_file, provider=args.provider
        )
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

    revised_entries_text: list[str] = []
    print(
        f"Found {len(entries)} entr{'y' if len(entries)==1 else 'ies'}; processing sequentially...",
        file=sys.stderr,
    )
    for idx, entry in enumerate(entries, start=1):
        key = entry.get("ID", f"entry_{idx}")
        print(f"Revising {idx}/{len(entries)}: {key}", file=sys.stderr)
        original_entry_text = _dump_single_entry(entry)
        separator = "=" * 80
        print(separator)
        print("--- BEFORE ---")
        print(original_entry_text.strip())
        try:
            revised_text = agent.revise_bibtex(original_entry_text, args.preferences)
            revised_entries_text.append(revised_text.strip())
            final_text = revised_text
        except Exception as e:
            print(
                f"Error revising entry '{key}': {str(e)} — keeping original",
                file=sys.stderr,
            )
            revised_entries_text.append(original_entry_text.strip())
            final_text = original_entry_text
        print("--- AFTER ----")
        print(final_text.strip())
        print(separator)

    combined = "\n\n".join(revised_entries_text) + "\n"

    if args.output:
        try:
            with open(args.output, "w") as f:
                f.write(combined)
            print(
                f"Revised {len(entries)} entries written to {args.output}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Error writing output: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        print(
            "No output file specified. Preview shown above; not writing output file.",
            file=sys.stderr,
        )
