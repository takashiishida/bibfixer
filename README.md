<div align="center">
<img src="logo.png" alt="" width="450">

[![PyPI version](https://badge.fury.io/py/bibfixer.svg?update=20250929)](https://pypi.org/project/bibfixer/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-blue.svg)
![Model](https://img.shields.io/badge/Model-GPT--5--mini-purple?logo=openai&logoColor=white)
[![Changelog](https://img.shields.io/github/v/release/takashiishida/bibfixer?label=changelog)](https://github.com/takashiishida/bibfixer/releases)
</div>

A Python tool that fixes and standardizes your BibTeX. It not only completes entries with accurate metadata via LLM + web search capabilities, but also enforces a consistent style based on your preferences (e.g., venue naming, title casing, author format, page ranges). This removes the tedious manual work of hunting down sources and cleaning messy entries (like those copied from Google Scholar), producing a clean, uniform bib file. A consistent style improves readability and leaves a stronger impression on readers and reviewers.

## Examples

Example (1) Original bib entry from Google Scholar. Additional authors are omitted and indicated by "and others", and "ai" is not capitalized.
```bib
@article{bai2022constitutional,
 author = {Bai, Yuntao and Kadavath, Saurav and Kundu, Sandipan and Askell, Amanda and Kernion, Jackson and Jones, Andy and Chen, Anna and Goldie, Anna and Mirhoseini, Azalia and McKinnon, Cameron and others},
 journal = {arXiv preprint arXiv:2212.08073},
 title = {Constitutional ai: Harmlessness from ai feedback},
 year = {2022}
}
```

With bibfixer, missing authors are added and title is capitalized properly:
```bib
@article{bai2022constitutional,
  author = {Bai, Yuntao and Kadavath, Saurav and Kundu, Sandipan and Askell, Amanda and Kernion, Jackson and Jones, Andy and Chen, Anna and Goldie, Anna and Mirhoseini, Azalia and McKinnon, Cameron and Chen, Carol and Olsson, Catherine and Olah, Christopher and Hernandez, Danny and Drain, Dawn and Ganguli, Deep and Li, Dustin and Tran-Johnson, Eli and Perez, Ethan and Kerr, Jamie and Mueller, Jared and Ladish, Jeffrey and Landau, Joshua and Ndousse, Kamal and Lukosuite, Kamile and Lovitt, Liane and Sellitto, Michael and Elhage, Nelson and Schiefer, Nicholas and Mercado, Noemi and DasSarma, Nova and Lasenby, Robert and Larson, Robin and Ringer, Sam and Johnston, Scott and Kravec, Shauna and El Showk, Sheer and Fort, Stanislav and Lanham, Tamera and Telleen-Lawton, Timothy and Conerly, Tom and Henighan, Tom and Hume, Tristan and Bowman, Samuel R. and Hatfield-Dodds, Zac and Mann, Ben and Amodei, Dario and Joseph, Nicholas and McCandlish, Sam and Brown, Tom and Kaplan, Jared},
  title = {Constitutional {AI}: {H}armlessness from {AI} Feedback},
  journal = {arXiv preprint arXiv:2212.08073},
  year = {2022}
}
```

Example (2) Original bib entry from Google Scholar. This shows the arXiv version but the paper was published in ICML. "llm" needs to be capitalized.
```bib
@article{khan2024debating,
 author = {Khan, Akbir and Hughes, John and Valentine, Dan and Ruis, Laura and Sachan, Kshitij and Radhakrishnan, Ansh and Grefenstette, Edward and Bowman, Samuel R and Rockt{\"a}schel, Tim and Perez, Ethan},
 journal = {arXiv preprint arXiv:2402.06782},
 title = {Debating with more persuasive llms leads to more truthful answers},
 year = {2024}
}
```

With bibfixer, arXiv is replaced with the conference information and appropriate title:
```bib
@inproceedings{khan2024debating,
  author = {Khan, Akbir and Hughes, John and Valentine, Dan and Ruis, Laura and Sachan, Kshitij and Radhakrishnan, Ansh and Grefenstette, Edward and Bowman, Samuel R. and Rockt{\"a}schel, Tim and Perez, Ethan},
  title = {Debating with More Persuasive {LLMs} Leads to More Truthful Answers},
  booktitle = {Proceedings of the 41st International Conference on Machine Learning},
  year = {2024},
  volume = {235},
  pages = {23662--23733}
}
```

Example (3) Original bib entry from Google Scholar. Last author is missing due to a system issue of the distributor Penguin Random House. Subtitle and publisher needs to be capitalized appropriately.
```bib
@book{sugiyama2022machine,
 title = {Machine learning from weak supervision: An empirical risk minimization approach},
 author = {Sugiyama, Masashi and Bao, Han and Ishida, Takashi and Lu, Nan and Sakai, Tomoya},
 year = {2022},
 publisher = {MIT Press}
}
```

With bibfixer, we have all authors and appropriate capitalization:
```bib
@book{sugiyama2022machine,
  author = {Sugiyama, Masashi and Bao, Han and Ishida, Takashi and Lu, Nan and Sakai, Tomoya and Niu, Gang},
  title = {Machine Learning from Weak Supervision: {A}n Empirical Risk Minimization Approach},
  publisher = {{MIT} Press},
  year = {2022},
  pages = {320}
}
```

## Installation

1. Install (from PyPI):
```bash
pip install bibfixer
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

## Usage

Basic usage (input is required via `-i/--input`):
```bash
bibfixer -i sample_input.bib
```

With output file:
```bash
bibfixer -i sample_input.bib -o corrected.bib
```

With additional formatting preferences (`-p`):
```bash
bibfixer -i sample_input.bib -p "Use NeurIPS instead of NIPS"
```

Use a custom prompt file (defaults to bundled `prompts/default.md`):
```bash
bibfixer -i sample_input.bib --prompt-file prompts/default.md
```

The complete revision instructions are in `prompts/default.md`. You can edit this file to match your style or point to another file using `--prompt-file`.

## Streamlit app

In addition to the dependencies in `pyproject.toml`, install `streamlit>=1.30.0`.

From the repo root, run:

```bash
streamlit run app.py
```

> [!WARNING]
> This tool uses LLM + web search and may occasionally produce incomplete or inaccurate metadata or formatting. Always review the final `.bib` before submission. To quickly compare input and output, you can run:
>
> ```bash
> diff -y --suppress-common-lines input.bib output.bib | less -R
> ```
