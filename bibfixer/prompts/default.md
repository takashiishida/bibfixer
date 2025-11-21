Instructions:

1) Find authoritative metadata
   - Search reputable sources (publisher site, proceedings page, openreview).
   - Prefer citing the peer‑reviewed journal or conference proceedings version over arXiv. Use arXiv only if no published version exists.
   - Even if you are sure about what the correct information should be, make sure to search the web for the most up-to-date information.

2) Verify and correct these fields
   - Authors: full names, correct order. Use BibTeX format `Last, First` with `and` separators.
   - Title: exact official title (be careful with capitalization, e.g., "ImageNet" instead of "Imagenet").
   - Venue: full journal name or full conference proceedings name.
   - Year: four digits.
   - Pages: use en‑dash style `123--145` when available.
   - Volume/Number: include for journal articles when available.
   - Entry type: `@article` for journals; `@inproceedings` for conference papers; `@book` for books, other types only when clearly appropriate.

3) Output formatting rules
   - Do NOT change the citation key (the part after `@type{` and before the comma). This is because I am already using this specific key in the paper.
   - For the `title` field, do NOT wrap the entire title in double curly braces (because we will be using a bst file to control what should and shouldn't be capitalized.)
   - Instead, use curly braces only around acronyms, proper nouns, the first character in the subtitle after the colon, and individual letters that must stay capitalized even when the BibTeX style downcases titles. For example:
     - `title = {Constitutional {AI}: {H}armlessness from {AI} Feedback},`
     - `title = {Debating with More Persuasive {LLMs} Leads to More Truthful Answers},`
     - `title = {Image{N}et Large Scale Visual Recognition Challenge},`
     - `title = {Attention Is All You Need},` (no extra braces needed).
   - Similarly, for `booktitle`, `journal`, and `publisher`, use braces only where needed to preserve capitalization of acronyms and proper names, for example:
     - `journal   = {{IEEE} Transactions on Pattern Analysis and Machine Intelligence},`
     - `publisher = {{MIT} Press},`
   - For authors, prefer `Last, First` form and separate authors with ` and `.
   - List all authors and do not use `et al.` or `and others` (even when there are hundreds of authors).
   - Use the full conference name in `booktitle` (no acronyms), e.g., `Proceedings of the 41st International Conference on Machine Learning` instead of `Proceedings of the 41st ICML`. Do not include the acronym after the full name, e.g., do not write `Proceedings of the 41st International Conference on Machine Learning (ICML)`.
   - For NeurIPS papers, the booktitle should be `Advances in Neural Information Processing Systems`, not `Proceedings of Neural Information Processing Systems`.
   - Field order (when present):
     `author`, `title`, `journal`/`booktitle`, `year`, `volume`, `number`, `pages`.
   - Indentation similar to typical BibTeX style and no trailing comma on the last field.
   - There is no formal proceedings in ICLR. Hence, start the page number from 1, e.g., `1--14`.
   - If we need to cite a web article/blog, use the access date written in the original bib entry. If the access date is missing in the original bib entry, or if it is written with a placeholder like `Accessed YYYY-MM-DD`, use the date of today.

4) Fields to OMIT
   - Do not include: URL, PDF link, DOI, editors, abstract, keywords in `@article` and `@proceedings`. For other types, use your best judgement.
   - If only an arXiv version exists, use `@article` and include `title`, `author`, `journal`, and `year`. For the `journal`, write `arXiv preprint arXiv:{ID}`, where you should write the arXiv ID for the placeholder.

5) If uncertain
   - Do not guess. Omit fields that cannot be verified from authoritative sources.

6) Output requirement
   - Return only a single, valid BibTeX entry. Do not include any explanations, prose, or Markdown code fences.


