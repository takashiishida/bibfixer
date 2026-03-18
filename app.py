import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibfixer.agent import BibFixAgent

st.set_page_config(
    page_title="BibFixer",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📚 BibFixer")
st.caption("Fix and complete BibTeX entries using LLM with web search.")

with st.sidebar:
    st.header("Settings")

    provider_display = st.selectbox(
        "Provider",
        options=["OpenAI", "OpenRouter"],
        index=0,
        help="Select the LLM provider.",
    )
    provider_key = provider_display.lower()

    if provider_key == "openai":
        api_key_label = "OpenAI API Key"
        api_key_env = "OPENAI_API_KEY"
    else:
        api_key_label = "OpenRouter API Key"
        api_key_env = "OPENROUTER_API_KEY"

    api_key = st.text_input(
        api_key_label,
        type="password",
        placeholder=f"Enter your {api_key_label} here",
        help=f"Used for {provider_display} API. Not stored.",
        value=os.getenv(api_key_env, ""),
    )

    if provider_key == "openai":
        model_friendly = st.selectbox(
            "Model",
            options=["gpt-5.2", "gpt-5-mini", "gpt-4.1"],
            index=0,
            help="Select the model to use. Default is gpt-5.2.",
        )
        model_map = {
            "gpt-5.2": "gpt-5.2-2025-12-11",
            "gpt-5-mini": "gpt-5-mini-2025-08-07",
            "gpt-4.1": "gpt-4.1",
        }
        selected_model = model_map.get(model_friendly, "gpt-5.2-2025-12-11")
    else:
        model_friendly = st.selectbox(
            "Model",
            options=[
                "anthropic/claude-sonnet-4.5",
                "openai/gpt-4.1",
                "google/gemini-2.5-flash",
                "anthropic/claude-3.5-haiku",
                "(custom)",
            ],
            index=0,
            help="Select the model to use, or choose (custom) to enter a model name.",
        )
        if model_friendly == "(custom)":
            selected_model = st.text_input(
                "Custom model name",
                placeholder="e.g., meta-llama/llama-4-maverick",
            )
        else:
            selected_model = model_friendly

    preferences = st.text_area(
        "Formatting Preferences",
        placeholder="e.g., 'Use sentence case for titles', 'abbreviate journal names'",
        height=120,
    )

    workers = st.number_input(
        "Workers",
        min_value=1,
        max_value=16,
        value=1,
        help="Number of parallel workers. Increase to speed up large .bib files.",
    )


bibtex_content = st.text_area(
    "BibTeX Content",
    height=240,
    placeholder="Paste your BibTeX entries here.",
)

if st.button("Fix BibTeX", type="primary"):
    # secrets/env fallback
    effective_api_key = (
        api_key
        or (st.secrets.get(api_key_env) if hasattr(st, "secrets") else None)
        or os.getenv(api_key_env)
    )

    if not effective_api_key:
        st.error(f"Please provide an API key for {provider_display} (input or in secrets/environment).")
    elif not bibtex_content:
        st.error("Please enter BibTeX content.")
    else:
        try:
            agent = BibFixAgent(api_key=effective_api_key, provider=provider_key)
            # Apply selected model to agent
            agent.model = selected_model
            db = bibtexparser.loads(bibtex_content)

            if not db.entries:
                st.warning("No BibTeX entries found.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                n = len(db.entries)

                def _process(i, entry):
                    entry_id = entry.get("ID", f"entry_{i+1}")
                    single_entry_db = BibDatabase()
                    single_entry_db.entries = [entry]
                    writer = BibTexWriter()
                    writer.order_entries_by = None
                    original_entry_text = writer.write(single_entry_db)
                    revised = agent.revise_bibtex(original_entry_text, preferences)
                    return i, entry_id, revised

                revised_entries = [None] * n
                done_count = 0
                with ThreadPoolExecutor(max_workers=int(workers)) as executor:
                    futures = {
                        executor.submit(_process, i, entry): i
                        for i, entry in enumerate(db.entries)
                    }
                    for future in as_completed(futures):
                        i, entry_id, revised = future.result()
                        revised_entries[i] = revised
                        done_count += 1
                        status_text.text(
                            f"Completed {done_count}/{n}: {entry_id}"
                        )
                        progress_bar.progress(done_count / n)

                status_text.text("Done!")
                combined = "\n\n".join(revised_entries)
                st.text_area("Revised BibTeX", combined, height=400)
                st.download_button(
                    "Download revised.bib",
                    combined.encode("utf-8"),
                    file_name="revised.bib",
                    mime="text/plain",
                )

        except Exception as e:
            st.error(f"An error occurred: {e}")
