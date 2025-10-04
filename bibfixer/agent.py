import os
import sys
from typing import Optional, Dict, Any
import bibtexparser
from openai import OpenAI
from importlib import resources


class BibFixAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_file: Optional[str] = None,
        provider: str = "openai",
    ):
        self.provider = provider.lower()
        self.api_key = api_key or self._get_default_api_key()
        if not self.api_key:
            raise ValueError(
                f"{self.provider.upper()} API key is required. Set {self._get_env_var_name()} environment variable or pass it as argument."
            )

        self.client = self._create_client()
        self.model = self._get_default_model()
        self.prompt_file_path = prompt_file

    def _get_default_api_key(self) -> Optional[str]:
        """Get default API key based on provider."""
        if self.provider == "openrouter":
            return os.getenv("OPENROUTER_API_KEY")
        return os.getenv("OPENAI_API_KEY")

    def _get_env_var_name(self) -> str:
        """Get environment variable name for the provider."""
        if self.provider == "openrouter":
            return "OPENROUTER_API_KEY"
        return "OPENAI_API_KEY"

    def _create_client(self) -> OpenAI:
        """Create OpenAI client configured for the selected provider."""
        if self.provider == "openrouter":
            return OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
            )
        elif self.provider == "openai":
            return OpenAI(api_key=self.api_key)
        else:
            raise ValueError(
                f"Unsupported provider: {self.provider}. Supported: 'openai', 'openrouter'"
            )

    def _get_default_model(self) -> str:
        """Get default model based on provider."""
        if self.provider == "openrouter":
            return "openai/gpt-4o"  # Default OpenRouter model
        return "gpt-5-mini-2025-08-07"  # Default OpenAI model

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
                    f"Failed to call OpenAI API: {str(e)} | Fallback also failed: {str(e2)}"
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
