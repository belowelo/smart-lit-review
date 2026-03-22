# smart-lit-review

a batch tool to automate your lit review from title + abstract + keywords!

this tool uses the semantic scholar API to fetch titles, abstracts, and semantic scholar pages of publications relevant to your paper, organizing them into different tier by order of importance.
i wouldn't use this as your primary lit review tool, but this works great as a secondary layer to catch things that you might have missed! 
simply download both files, place them in a clean folder, then run 'start here!.bat'!
 
  ## output tiers

  | tier | meaning |
  |------|---------|
  | seed | papers you provided by DOI |
  | 0 | published in your target venue or by editorial board members |
  | 1 | appeared in 3+ searches, or 2+ with high citations |
  | 2 | appeared in 2+ searches |
  | 3 | everything else (title-only scan list) |
