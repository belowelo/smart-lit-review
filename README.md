# smart-lit-review

a batch tool to automate your lit review from title + abstract + keywords!

this tool uses the semantic scholar API to fetch titles, abstracts, and semantic scholar pages of publications relevant to your paper, organizing them into different tier by order of importance.
AS semantic scholar does have several coverage gaps (in the humanities, especially!) i wouldn't use this as your primary lit review tool, but this works great as a secondary layer to catch things that you might have missed!  

  ## setup
  1. apply for a free API key at https://www.semanticscholar.org/product/api#api-key (or email me, if you know me personally)
  2. place both start here.bat and lit-review.py in a fresh directory, and run start here.bat!

  ## this tool takes...
  1. your title
  2. your prospective keywords
  3. your abstract
  4. target venues
  5. editorial board of target venues
  6. additional search terms
  7. dois of papers you already know you'll cite
 
  ## ...and outputs the following in a simple markdown file:

  **title; # of overlapping search results; importance tier score; author; venue; doi; abstract.**
  
  the tiering logic is quite simple: 

  | tier | meaning |
  |------|---------|
  | seed | papers you provided by DOI |
  | 0: must reads | published in your target venue or by editorial board members |
  | 1: important papers | appeared in 3+ searches, or 2+ with high citations |
  | 2: check-worthy abstracts | appeared in 2+ searches |
  | 3: other search results | a list of every other paper that appeared in the search, by title. |
  
  ## methodology
  in order to replicate the results of systematic reading/lit review methodologies, search results are tiered via multi-pass overlap under the assumption that a text will be more relevant if it appears multiple times across various independently-construed search angles.
 
  these search passes include:
  - your title, verbatim
  - pairwise combinations of your keywords, ordered by importance (A, B, C, D -> AB, AC, AD, BC, BD, etc.)
  - regex extractions from your abstract (quoted terms, capitalized proper nouns)
  - your target venues and the relevant board members of said target venue + your top 3 keywords (2022+)
  - any additional search terms you might specify
  - a broader recency sweep of the top 3 keywords (2024+) 
  - citation-chain-traversal from the bibliography/forward citations of seeded and tier 1+ publications.

  these search results are then tiered/internally ordered (within the tiers) via overlap count, citation count, board membership of authors, and recency.

  ## disclosure
  the creation of this tool (limited strictly to python scripting) was LLM-assisted and is not intended for commercial use. 
  as such, this tool contains jank, but should be enough to support the work of early-career scholars and students during their second-pass lit review. as you might be able to tell from the tool requiring a fully written abstract and keywords to function properly, **this tool is intended moreso to be a checking/verification tool, not a primary research tool!**
  
  however, the actual python script **contains NO machine-learning technology** whatsoever; just API calling, text processing through python and YAML, and regex to automate searching/browsing in bulk. again, **this tool does NOT write the lit review for you**. (semantic scholar itself indexes papers utilizing embeddings, though.) 
  
  the intention of this tool was to create creating a reusable search script to _reduce_ LLM usage by early-career scholars and minimize dependency overall. scholarship and literature review methodologies utilizing LLM-embedded summarization tools such as ellicit and semantic scholar have become commonplace, but a researcher unfamiliar with semantic embedding will have difficulty optimizing and targeting their search methods. this tool utilizes non-LLM tools to make this process more efficient, minimizing dummy searches while keeping the search net academically robust. 
