"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
  from agent import run_agent
  from utils.data_loader import get_example_wardrobe

  result = run_agent(
      query="vintage graphic tee under $30, size M",
      wardrobe=get_example_wardrobe(),
  )
  print(result["fit_card"])
  print(result["error"])   # None on success
"""

import re

from tools import searchListings, suggestOutfit, createFitCard


# ── session state ─────────────────────────────────────────────────────────────

def _newSession(query: str, wardrobe: dict) -> dict:
  """
  Initialize and return a fresh session dict for one user interaction.

  The session dict is the single source of truth for everything that happens
  during a run — it stores the original query, parsed parameters, tool results,
  and any error that caused early termination.

  You may add fields to this dict as needed for your implementation.
  """
  return {
    "query": query,              # original user query
    "parsed": {},                # extracted description / size / max_price
    "search_results": [],        # list of matching listing dicts
    "selected_item": None,       # top result, passed into suggest_outfit
    "wardrobe": wardrobe,        # user's wardrobe dict
    "outfit_suggestion": None,   # string returned by suggest_outfit
    "fit_card": None,            # string returned by create_fit_card
    "error": None,               # set if the interaction ended early
  }


# ── planning loop ─────────────────────────────────────────────────────────────

def runAgent(query: str, wardrobe: dict) -> dict:
  """
  Main agent entry point. Runs the FitFindr planning loop for a single
  user interaction and returns the completed session dict.

  Args:
      query:    Natural language user request
                (e.g., "vintage graphic tee under $30, size M")
      wardrobe: User's wardrobe dict — use getExampleWardrobe() or
                getEmptyWardrobe() from utils/dataLoader.py

  Returns:
      The session dict after the interaction completes. Check session["error"]
      first — if it is not None, the interaction ended early and the other
      output fields (outfit_suggestion, fit_card) will be None.
  """
  session = _newSession(query, wardrobe)

  # Step 2: Parse the query with regex to extract price, size, and description.
  # Price: "under $30", "$40", "max $50", "less than $25", "below $60"
  priceMatch = re.search(r'(?:under|max|less\s+than|below|up\s+to)?\s*\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
  maxPrice = float(priceMatch.group(1)) if priceMatch else None

  # Size: "size M", "size XL", shoe sizes like "US 8", waist like "W30"
  sizeMatch = re.search(
    r'\b(?:size\s+)?(XXS|XS|XXL|XL|S\/M|M\/L|L\/XL|[SML]|W\d{2}(?:\s*L\d{2})?|US\s*\d+(?:\.\d+)?|UK\s*\d+(?:\.\d+)?)\b',
    query, re.IGNORECASE
  )
  size = sizeMatch.group(1) if sizeMatch else None

  # Description: strip price and size phrases so scoring focuses on content words
  description = query
  if priceMatch: description = description.replace(priceMatch.group(0), " ")
  if sizeMatch: description = re.sub(r'\b(?:size\s+)?' + re.escape(sizeMatch.group(1)), " ", description, flags=re.IGNORECASE)
  description = re.sub(r'\s+', ' ', description).strip(" ,.")

  session["parsed"] = {"description": description, "size": size, "max_price": maxPrice}

  # Step 3: Search listings
  results = searchListings(description=description, size=size, maxPrice=maxPrice)
  session["search_results"] = results
  print("State after searchListings:", session)
  print("\n")

  if not results:
    hints = []
    if maxPrice: hints.append("raise your price limit")
    if size: hints.append("remove the size filter")
    hints.append("try broader style keywords")
    session["error"] = (f"No listings found for \"{query}\".\nTry: {', '.join(hints)}.")

    return session

  session["selected_item"] = results[0]
  session["outfit_suggestion"] = suggestOutfit(results[0], wardrobe)
  print("State after suggestOutfit:", session)
  print("\n")
  session["fit_card"] = createFitCard(session["outfit_suggestion"], results[0])
  print("State after createFitCard:", session)
  print("\n\n")

  return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
  from utils.dataLoader import getExampleWardrobe, getEmptyWardrobe

  print("=== Happy path: graphic tee ===\n")
  session = runAgent(query="looking for a vintage graphic tee under $30", wardrobe=getExampleWardrobe())
  if session["error"]: print(f"Error: {session['error']}")
  else:
    print(f"Found: {session['selected_item']['title']}")
    print(f"\nOutfit: {session['outfit_suggestion']}")
    print(f"\nFit card: {session['fit_card']}")

  print("\n\n=== No-results path ===\n")
  session2 = runAgent(query="designer ballgown size XXS under $5", wardrobe=getExampleWardrobe())
  print(f"Error message: {session2['error']}")