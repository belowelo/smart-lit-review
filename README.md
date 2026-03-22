# smart-lit-review

a batch tool to automate your lit review from title + abstract + keywords!

this tool uses the semantic scholar API to fetch titles, abstracts, and semantic scholar pages of publications relevant to your paper, organizing them into different tier by order of importance.
i wouldn't use this as your primary lit review tool, but this works great as a secondary layer to catch things that you might have missed! 

  ## setup
  1. install python 3.8+
  2. run `pip install requests pyyaml`
  3. grab a free API key at https://www.semanticscholar.org/product/api#api-key
  4. place both start here.bat and lit-review.py in a fresh directory, and run start here.bat!

  ## this tool takes...
  1. your title
  2. your prospective keywords
  3. your abstract
  4. target venues
  5. editorial board of target venues
  6. additional search terms
  7. dois of papers you already know you'll cite
 
  ## ...and outputs the following in a markdown file:

  | tier | meaning |
  |------|---------|
  | seed | papers you provided by DOI |
  | 0: must reads | published in your target venue or by editorial board members |
  | 1: important papers | appeared in 3+ searches, or 2+ with high citations |
  | 2: check-worthy abstracts | appeared in 2+ searches |
  | 3: other search results | a list of every other paper that appeared in the search, by title. |

  ## disclosure
  the creation of this tool was LLM-assisted (what isn't nowadays, really :/) and is not intended for commercial distribution or use! 
  i used my institution's LLM subscription with the intention of creating a reusable script to replace the usecases of LLM by some scholars in my department in order to minimize dependency and optimize usage overall.
  
  as such, this tool contains jank, but should be enough to support the work of early-career scholars and students during their second-pass lit review.
