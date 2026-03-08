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
    SUPPORTED_PROVIDERS = ("openai", "openrouter")
    DEFAULT_MODELS = {
        "openai": "gpt-5.2-2025-12-11",
        "openrouter": "anthropic/claude-sonnet-4.5",
    }

    def __init__(self, api_key: Optional[str] = None, prompt_file: Optional[str] = None, provider: str = "openai"):
        self.provider = provider.lower()
        if self.provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. Choose from: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )

        if self.provider == "openrouter":
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable or pass it as argument."
                )
            self.client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
        else:
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it as argument."
                )
            self.client = OpenAI(api_key=self.api_key)

        self.model = self.DEFAULT_MODELS[self.provider]
        self.prompt_file_path = prompt_file

    def _load_instructions_from_file(self) -> Optional[str]:
        if self.prompt_file_path:
            try:
                if os.path.exists(self.prompt_file_path):
                    with open(self.prompt_file_path, "r", encoding="utf-8") as f:
                        return f.read().strip() + "\n"
            except Exception:
                pass
        try:
            with resources.files("bibfixer.prompts").joinpath("default.md").open(
                "r", encoding="utf-8"
            ) as f:
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

    def _call_chat_completions(self, prompt: str, model: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
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

    def revise_bibtex(self, bibtex_string: str, user_preferences: str = "") -> str:
        parsed = self.parse_bibtex(bibtex_string)
        prompt = self._create_prompt(bibtex_string, parsed, user_preferences)

        if self.provider == "openrouter":
            return self._revise_openrouter(prompt)
        else:
            return self._revise_openai(prompt)

    def _revise_openai(self, prompt: str) -> str:
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
                return self._call_chat_completions(prompt, self.model)
            except Exception as e2:
                raise RuntimeError(
                    f"Failed to call OpenAI API: {str(e)} | Fallback also failed: {str(e2)}"
                )

    def _revise_openrouter(self, prompt: str) -> str:
        # Append :online suffix to enable web search via Exa.ai
        model = self.model
        if not model.endswith(":online"):
            model = model + ":online"
        try:
            return self._call_chat_completions(prompt, model)
        except Exception as e:
            raise RuntimeError(f"Failed to call OpenRouter API: {str(e)}")

    def _create_prompt(
        self, original_bibtex: str, parsed: Dict[str, Any], preferences: str
    ) -> str:
        title = parsed["title"]
        first_author = parsed["first_author"]
        if self.provider == "openai":
            intro = "Please search the web for the following academic paper and correct/complete its BibTeX entry:"
        else:
            intro = "Using your knowledge and any available search capabilities, correct/complete the following BibTeX entry:"

        prompt = f"""{intro}

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
            raise FileNotFoundError(
                "Prompt file not found or unreadable. Cannot proceed without detailed instructions."
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


