"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
  searchListings(description, size, maxPrice)  → list[dict]
  suggestOutfit(newItem, wardrobe)              → str
  createFitCard(outfit, newItem)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.dataLoader import loadListings

load_dotenv()

_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _getGroqClient():
  """Initialize and return a Groq client using GROQ_API_KEY from .env."""
  apiKey = os.environ.get("GROQ_API_KEY")
  if not apiKey:
    raise ValueError("GROQ_API_KEY not set. Add it to a .env file in the project root.")

  return Groq(api_key=apiKey)


# ── Tool 1: searchListings ────────────────────────────────────────────────────

def searchListings(description: str, size: str | None = None, maxPrice: float | None = None) -> list[dict]:
  """
  Search the mock listings dataset for items matching the description,
  optional size, and optional price ceiling.

  Args:
      description: Keywords describing what the user is looking for
                    (e.g., "vintage graphic tee").
      size:        Size string to filter by, or None to skip size filtering.
                    Matching is case-insensitive (e.g., "M" matches "S/M").
      maxPrice:    Maximum price (inclusive), or None to skip price filtering.

  Returns:
      A list of matching listing dicts, sorted by relevance (best match first).
      Returns an empty list if nothing matches — does NOT raise an exception.
  """
  listings = loadListings()

  # Filter by price
  if maxPrice is not None: listings = [l for l in listings if l["price"] <= maxPrice]

  # Filter by size — split listing size into tokens and check for a match
  if size:
    sizeLower = size.lower().strip()
    def sizeMatches(listingSize: str) -> bool:
      tokens = re.findall(r'\w+', listingSize.lower())
      return sizeLower in tokens
    listings = [l for l in listings if sizeMatches(l["size"])]

  # Score each listing by keyword overlap with the description
  keywords = set(re.findall(r'\w+', description.lower()))
  # Remove common stop words that add noise without meaning
  stopWords = {"a", "an", "the", "in", "for", "of", "and", "or", "to", "at", "on", "with", "under", "size", "looking"}
  keywords -= stopWords

  def score(listing: dict) -> int:
    text = " ".join([
      listing.get("title", ""),
      listing.get("description", ""),
      listing.get("category", ""),
      listing.get("brand", "") or "",
      " ".join(listing.get("style_tags", [])),
      " ".join(listing.get("colors", [])),
    ]).lower()
    words = set(re.findall(r'\w+', text))

    return len(keywords & words)

  scored = [(score(l), l) for l in listings]
  scored = [(s, l) for s, l in scored if s > 0]
  scored.sort(key=lambda x: x[0], reverse=True)

  return [l for _, l in scored]


# ── Tool 2: suggestOutfit ─────────────────────────────────────────────────────

def suggestOutfit(newItem: dict, wardrobe: dict) -> str:
  """
  Given a thrifted item and the user's wardrobe, suggest 1-2 complete outfits.

  Args:
      newItem:  A listing dict (the item the user is considering buying).
      wardrobe: A wardrobe dict with an 'items' key. May be empty.

  Returns:
      A non-empty string with outfit suggestions. If the wardrobe is empty,
      returns general styling advice rather than raising an exception.
  """
  client = _getGroqClient()
  items = wardrobe.get("items", [])

  itemDetails = (
    f"Name: {newItem['title']}\n"
    f"Category: {newItem['category']}\n"
    f"Colors: {', '.join(newItem['colors'])}\n"
    f"Style: {', '.join(newItem['style_tags'])}\n"
    f"Description: {newItem['description']}"
  )

  if not items:
    prompt = (
      f"You're a personal stylist. A user just found this secondhand item:\n{itemDetails}\n\n"
      "They don't have a wardrobe on file yet (new user). Give them 2 general styling suggestions — "
      "what kinds of pieces pair well with this item, what vibe it creates, and how to wear it. "
      "Keep it casual, specific, and practical."
    )
  else:
    wardrobeText = "\n".join(
      f"- {item['name']} ({item['category']}, colors: {', '.join(item['colors'])}, style: {', '.join(item['style_tags'])})"
      for item in items
    )
    prompt = (
      f"You're a personal stylist. A user just found this secondhand item:\n{itemDetails}\n\n"
      f"Their current wardrobe:\n{wardrobeText}\n\n"
      "Suggest 1-2 specific outfit combinations using this new item with named pieces from their wardrobe. "
      "Be specific about which wardrobe items to pair together and why it works. Keep it casual and practical."
    )

  response = client.chat.completions.create(
    model=_MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
    max_tokens=400,
  )

  return response.choices[0].message.content.strip()


# ── Tool 3: createFitCard ─────────────────────────────────────────────────────

def createFitCard(outfit: str, newItem: dict) -> str:
  """
  Generate a short, shareable outfit caption for the thrifted find.

  Args:
      outfit:   The outfit suggestion string from suggestOutfit().
      newItem:  The listing dict for the thrifted item.

  Returns:
      A 2-4 sentence caption string. If outfit is empty, returns an error
      message string — does NOT raise an exception.
  """
  if not outfit or not outfit.strip(): return "Couldn't generate a fit card — outfit details are missing. Try searching for an item first."

  client = _getGroqClient()
  prompt = (
    f"You're writing an Instagram/TikTok OOTD caption for a thrift find. "
    f"Keep it casual and authentic — like a real person posting their outfit, not a brand.\n\n"
    f"The thrifted item:\n"
    f"- Name: {newItem['title']}\n"
    f"- Price: ${newItem['price']:.2f}\n"
    f"- Platform: {newItem['platform']}\n\n"
    f"The outfit:\n{outfit}\n\n"
    "Write a 2-4 sentence caption that:\n"
    "- Feels like a real OOTD post (casual, fun, specific about the vibe)\n"
    "- Mentions the item name, price, and platform naturally (each once)\n"
    "- Ends with 3-5 relevant hashtags\n\n"
    "Just the caption and hashtags — no quotes, no preamble."
  )

  response = client.chat.completions.create(
    model=_MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.9,
    max_tokens=250,
  )

  return response.choices[0].message.content.strip()