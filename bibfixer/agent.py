import os
import sys
from typing import Optional, Dict, Any
import json
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from openai import OpenAI
from importlib import resources


class BibFixAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_file: Optional[str] = None,
        model: Optional[str] = None,
        router: str = "openai",
        openrouter_referer: Optional[str] = None,
        openrouter_title: Optional[str] = None,
        use_structured_output: bool = False,
    ):
        self.router = (router or "openai").lower()
        self.model = model or "gpt-5-mini-2025-08-07"
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
            }
        except Exception as e:
            raise ValueError(f"Failed to parse BibTeX: {str(e)}")

    def revise_bibtex(self, bibtex_string: str, user_preferences: str = "") -> str:
        # Use structured agent if requested and router is OpenAI
        if self.use_structured_output and self.router == "openai":
            try:
                from .structured_agent import StructuredBibFixAgent

                structured_agent = StructuredBibFixAgent(
                    api_key=self.api_key,
                    prompt_file=self.prompt_file_path,
                    model=self.model,
                    router=self.router,
                    use_structured_output=True,
                )
                return structured_agent.revise_bibtex(bibtex_string, user_preferences)
            except Exception as e:
                print(
                    f"Structured output failed ({str(e)}), falling back to traditional method",
                    file=sys.stderr,
                )

        # Traditional method
        parsed = self.parse_bibtex(bibtex_string)
        prompt = self._create_prompt(bibtex_string, parsed, user_preferences)
        try:
            full_prompt = (
                """You are a precise academic assistant that corrects and completes BibTeX entries. Always return valid BibTeX format.

"""
                + prompt
            )
            response = self.client.responses.create(
                model=self.model, input=full_prompt, tools=[{"type": "web_search"}]
            )
            revised_bibtex = None
            if hasattr(response, "output_text"):
                revised_bibtex = getattr(response, "output_text", None)
            elif hasattr(response, "__iter__"):
                for item in response:
                    if hasattr(item, "type") and item.type == "message":
                        if hasattr(item, "content") and item.content:
                            for content_item in item.content:
                                if hasattr(content_item, "text"):
                                    revised_bibtex = content_item.text
                                    break
                        break
            elif hasattr(response, "output"):
                revised_bibtex = response.output
            else:
                revised_bibtex = str(response)
            if not revised_bibtex:
                raise ValueError("Could not extract BibTeX from response")
            try:
                bibtexparser.loads(revised_bibtex)
            except Exception:
                print(
                    "Warning: Response may not be valid BibTeX format", file=sys.stderr
                )
            return revised_bibtex
        except Exception as e:
            try:
                print(
                    f"Note: Responses API failed ({str(e)}), falling back to chat completions API without web search",
                    file=sys.stderr,
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
                )
                revised_bibtex = response.choices[0].message.content
                try:
                    bibtexparser.loads(revised_bibtex)
                except Exception:
                    print(
                        "Warning: Response may not be valid BibTeX format",
                        file=sys.stderr,
                    )
                return revised_bibtex
            except Exception as e2:
                raise RuntimeError(
                    f"Failed to call API: {str(e)} | Fallback also failed: {str(e2)}"
                )

    def _create_prompt(
        self, original_bibtex: str, parsed: Dict[str, Any], preferences: str
    ) -> str:
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
