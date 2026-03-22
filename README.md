# smart-lit-review

a batch tool to automate your lit review from title + abstract + keywords!

this tool uses the semantic scholar API to fetch titles, abstracts, and semantic scholar pages of publications relevant to your paper, organizing them into different tier by order of importance.
i wouldn't use this as your primary lit review tool, but this works great as a secondary layer to catch things that you might have missed! 
simply download both files, place them in a clean folder, then run 'start here!.bat'!

  ## input info
  1. your title
  2. your prospective keywords
  3. your abstract
  4. target venues
  5. editorial board of target venues
  6. additional search terms
  7. DOIs of papers you already know you'll cite!
 
  ## output tiers

  | tier | meaning |
  |------|---------|
  | seed | papers you provided by DOI |
  | 0 | must reads | published in your target venue or by editorial board members |
  | 1 | important papers | appeared in 3+ searches, or 2+ with high citations |
  | 2 | check-worthy abstracts | appeared in 2+ searches |
  | 3 | other search results | a list of every other paper that appeared in the search, by title. |
