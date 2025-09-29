import os
import sys
from typing import Optional, Dict, Any, Literal
import json
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from openai import OpenAI
from importlib import resources
from pydantic import BaseModel, Field


class BibTexEntry(BaseModel):
    """Pydantic model for structured BibTeX entry output"""

    entry_type: Literal[
        "article",
        "inproceedings",
        "book",
        "incollection",
        "inbook",
        "misc",
        "phdthesis",
        "mastersthesis",
        "techreport",
        "unpublished",
    ] = Field(
        description="Type of the BibTeX entry (e.g., article, inproceedings, book)"
    )
    citation_key: str = Field(
        description="The citation key used to reference this entry (should be kept unchanged from original)"
    )
    author: str = Field(
        description="Authors in BibTeX format: 'Last, First and Last2, First2' - use full names, correct order"
    )
    title: str = Field(
        description="Exact official title of the work, preserving capitalization"
    )
    year: str = Field(description="Publication year (four digits)")
    # Optional fields that may or may not be present
    journal: Optional[str] = Field(
        None, description="Journal name for articles (full name, not abbreviated)"
    )
    booktitle: Optional[str] = Field(
        None,
        description="Conference proceedings name for inproceedings (full name, no acronyms)",
    )
    volume: Optional[str] = Field(None, description="Volume number for journals")
    number: Optional[str] = Field(None, description="Issue number for journals")
    pages: Optional[str] = Field(
        None, description="Page range using en-dash format (e.g., 123--145)"
    )
    publisher: Optional[str] = Field(
        None, description="Publisher name for books and some conferences"
    )
    address: Optional[str] = Field(None, description="Publisher location")
    series: Optional[str] = Field(
        None, description="Series name for books or conference proceedings"
    )
    edition: Optional[str] = Field(None, description="Edition number for books")
    chapter: Optional[str] = Field(None, description="Chapter number for book chapters")
    note: Optional[str] = Field(None, description="Additional notes")
    organization: Optional[str] = Field(None, description="Sponsoring organization")
    school: Optional[str] = Field(None, description="School name for theses")
    institution: Optional[str] = Field(
        None, description="Institution name for technical reports"
    )


class StructuredBibFixAgent:
    """
    Enhanced BibFixer agent that uses OpenAI's JSON Schema functionality
    to enforce structured BibTeX output format for better reliability.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_file: Optional[str] = None,
        model: Optional[str] = None,
        router: str = "openai",
        openrouter_referer: Optional[str] = None,
        openrouter_title: Optional[str] = None,
        use_structured_output: bool = True,
    ):
        self.router = (router or "openai").lower()
        self.model = (
            model or "gpt-5-mini-2025-08-07"
        )  # Use a model that supports structured outputs
        self.prompt_file_path = prompt_file
        self.use_structured_output = use_structured_output

        if self.router == "openrouter":
            # Prefer explicit key, then OPENROUTER_API_KEY
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenRouter API key is required. Set OPENROUTER_API_KEY or pass api_key."
                )
            base_url = "https://openrouter.ai/api/v1"
            default_headers: Dict[str, str] = {}
            referer = openrouter_referer or os.getenv("HTTP_REFERER")
            title = openrouter_title or os.getenv("X_TITLE")
            if referer:
                default_headers["HTTP-Referer"] = referer
            if title:
                default_headers["X-Title"] = title
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                default_headers=default_headers if default_headers else None,
            )
        else:
            # OpenAI default
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it as argument."
                )
            self.client = OpenAI(api_key=self.api_key)

    def _load_instructions_from_file(self) -> Optional[str]:
        """Load instructions from file or default prompt"""
        if self.prompt_file_path:
            try:
                if os.path.exists(self.prompt_file_path):
                    with open(self.prompt_file_path, "r", encoding="utf-8") as f:
                        return f.read().strip() + "\n"
            except Exception:
                pass
        try:
            with (
                resources.files("bibfixer.prompts")
                .joinpath("default.md")
                .open("r", encoding="utf-8") as f
            ):
                return f.read().strip() + "\n"
        except Exception:
            return None

    def parse_bibtex(self, bibtex_string: str) -> Dict[str, Any]:
        """Parse BibTeX string to extract basic info"""
        try:
            bib_database = bibtexparser.loads(bibtex_string)
            if not bib_database.entries:
                raise ValueError("No valid BibTeX entries found")
            entry = bib_database.entries[0]
            title = entry.get("title", "").strip("{}")
            authors_str = entry.get("author", "")
            if authors_str:
                if " and " in authors_str:
                    first_author = authors_str.split(" and ")[0].strip()
                elif "," in authors_str:
                    first_author = authors_str.split(",")[0].strip()
                else:
                    first_author = authors_str.strip()
            else:
                first_author = ""
            return {
                "original_entry": entry,
                "title": title,
                "first_author": first_author,
                "entry_type": entry.get("ENTRYTYPE", "article"),
                "citation_key": entry.get("ID", "unknown"),
            }
        except Exception as e:
            raise ValueError(f"Failed to parse BibTeX: {str(e)}")

    def _structured_entry_to_bibtex(self, structured_entry: BibTexEntry) -> str:
        """Convert structured entry back to BibTeX format"""
        lines = [f"@{structured_entry.entry_type}{{{structured_entry.citation_key},"]

        # Define field order for consistent output
        field_order = [
            "author",
            "title",
            "journal",
            "booktitle",
            "year",
            "volume",
            "number",
            "pages",
            "publisher",
            "address",
            "series",
            "edition",
            "chapter",
            "note",
            "organization",
            "school",
            "institution",
        ]

        for field in field_order:
            value = getattr(structured_entry, field, None)
            if value is not None and value.strip():
                # Special handling for title to preserve capitalization
                if field == "title":
                    formatted_value = f"{{{{{value}}}}}"
                else:
                    formatted_value = f"{{{value}}}"
                lines.append(f"  {field} = {formatted_value},")

        # Remove trailing comma from last field
        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]

        lines.append("}")
        return "\n".join(lines)

    def revise_bibtex(self, bibtex_string: str, user_preferences: str = "") -> str:
        """Revise BibTeX entry using structured output for better reliability"""
        parsed = self.parse_bibtex(bibtex_string)

        if self.use_structured_output and self.router == "openai":
            return self._revise_bibtex_structured(
                bibtex_string, parsed, user_preferences
            )
        else:
            # Fallback to original method
            return self._revise_bibtex_traditional(
                bibtex_string, parsed, user_preferences
            )

    def _revise_bibtex_structured(
        self, bibtex_string: str, parsed: Dict[str, Any], user_preferences: str
    ) -> str:
        """Use OpenAI structured outputs with JSON Schema"""
        prompt = self._create_structured_prompt(bibtex_string, parsed, user_preferences)

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise academic assistant that corrects and completes BibTeX entries. Use web search to find authoritative information and return a properly structured BibTeX entry.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=BibTexEntry,
                temperature=0.1,  # Lower temperature for more consistent formatting
            )

            structured_entry = response.choices[0].message.parsed
            if structured_entry is None:
                raise ValueError("Failed to parse structured response")

            # Convert back to BibTeX format
            revised_bibtex = self._structured_entry_to_bibtex(structured_entry)

            # Validate the generated BibTeX
            try:
                bibtexparser.loads(revised_bibtex)
            except Exception as e:
                print(
                    f"Warning: Generated BibTeX may have formatting issues: {e}",
                    file=sys.stderr,
                )

            return revised_bibtex

        except Exception as e:
            print(
                f"Structured output failed ({str(e)}), falling back to traditional method",
                file=sys.stderr,
            )
            return self._revise_bibtex_traditional(
                bibtex_string, parsed, user_preferences
            )

    def _revise_bibtex_traditional(
        self, bibtex_string: str, parsed: Dict[str, Any], user_preferences: str
    ) -> str:
        """Traditional method as fallback"""
        prompt = self._create_prompt(bibtex_string, parsed, user_preferences)

        try:
            full_prompt = (
                """You are a precise academic assistant that corrects and completes BibTeX entries. Always return valid BibTeX format.

"""
                + prompt
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise academic assistant that corrects and completes BibTeX entries. Always return valid BibTeX format. Use your knowledge to correct and complete the entry as best as you can.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            revised_bibtex = response.choices[0].message.content

            try:
                bibtexparser.loads(revised_bibtex)
            except Exception:
                print(
                    "Warning: Response may not be valid BibTeX format", file=sys.stderr
                )

            return revised_bibtex

        except Exception as e:
            raise RuntimeError(f"Failed to call API: {str(e)}")

    def _create_structured_prompt(
        self, original_bibtex: str, parsed: Dict[str, Any], preferences: str
    ) -> str:
        """Create prompt optimized for structured output"""
        title = parsed["title"]
        first_author = parsed["first_author"]
        citation_key = parsed["citation_key"]

        prompt = f"""Please search for authoritative information about this academic paper and provide a corrected BibTeX entry:

Title: "{title}"
First Author: {first_author if first_author else "(unknown)"}
Citation Key: {citation_key} (DO NOT CHANGE THIS)

Original BibTeX entry:
```bibtex
{original_bibtex}
```

CRITICAL: The citation_key field MUST be exactly "{citation_key}" - do not change it.
"""

        external_instructions = self._load_instructions_from_file()
        if external_instructions:
            prompt += "\n" + external_instructions
        else:
            print(
                "Warning: prompt file not found or unreadable; proceeding without detailed instructions.",
                file=sys.stderr,
            )

        if preferences:
            prompt += f"""
Additional user preferences for formatting:
{preferences}
"""

        prompt += """
Return the entry data in the structured format. Make sure to:
- Keep the original citation_key unchanged
- Use proper BibTeX author format: "Last, First and Last2, First2"
- Include complete, accurate information from authoritative sources
- Follow all formatting rules from the instructions above
"""
        return prompt

    def _create_prompt(
        self, original_bibtex: str, parsed: Dict[str, Any], preferences: str
    ) -> str:
        """Create traditional prompt (fallback method)"""
        title = parsed["title"]
        first_author = parsed["first_author"]

        prompt = f"""Please search the web for the following academic paper and correct/complete its BibTeX entry:

Title: "{title}"
First Author: {first_author if first_author else "(unknown)"}

Original BibTeX entry:
```bibtex
{original_bibtex}
```
"""
        external_instructions = self._load_instructions_from_file()
        if external_instructions:
            prompt += "\n" + external_instructions
        else:
            print(
                "Warning: prompt file not found or unreadable; proceeding without detailed instructions.",
                file=sys.stderr,
            )
        if preferences:
            prompt += f"""
5. Apply these user preferences to the formatting:
{preferences}
"""
        prompt += """
Return ONLY the corrected BibTeX entry, properly formatted. Do not include any explanation or additional text.
"""
        return prompt
