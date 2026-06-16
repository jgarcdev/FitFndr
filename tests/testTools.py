"""
tests/test_tools.py

Pytest suite for the three FitFindr tools: searchListings, suggestOutfit,
and createFitCard. LLM calls (suggestOutfit, createFitCard) are mocked so
tests run without a live Groq API key.
"""

import re
import pytest
from unittest.mock import MagicMock, patch

from tools import searchListings, suggestOutfit, createFitCard


SAMPLE_ITEM = {
  "id": "lst_001",
  "title": "Vintage Levi's 501 Jeans — Medium Wash",
  "description": "Classic 501s in a perfect medium wash.",
  "category": "bottoms",
  "style_tags": ["vintage", "classic", "denim", "streetwear"],
  "size": "W30 L30",
  "condition": "good",
  "price": 38.00,
  "colors": ["blue", "indigo"],
  "brand": "Levi's",
  "platform": "depop",
}

POPULATED_WARDROBE = {
  "items": [
    {
      "name": "White Oversized Tee",
      "category": "tops",
      "colors": ["white"],
      "style_tags": ["casual", "minimalist"],
    },
    {
      "name": "Black Skinny Jeans",
      "category": "bottoms",
      "colors": ["black"],
      "style_tags": ["classic", "streetwear"],
    },
  ]
}

EMPTY_WARDROBE = {"items": []}


@pytest.fixture
def mockGroq():
  mockMessage = MagicMock()
  mockMessage.content = "Here are your outfit suggestions."

  mockChoice = MagicMock()
  mockChoice.message = mockMessage

  mockResponse = MagicMock()
  mockResponse.choices = [mockChoice]

  mockClient = MagicMock()
  mockClient.chat.completions.create.return_value = mockResponse

  with patch("tools._getGroqClient", return_value=mockClient):
    yield mockClient


class TestSearchListings:
  def testReturnsList(self):
    assert isinstance(searchListings("jeans"), list)

  def testKeywordMatchReturnsRelevantResults(self):
    results = searchListings("denim jeans vintage")
    assert len(results) > 0
    titlesAndTags = [" ".join([r["title"], " ".join(r["style_tags"]) ]).lower() for r in results]
    assert any("denim" in t or "jean" in t or "vintage" in t for t in titlesAndTags)

  def testNoMatchReturnsEmptyList(self):
    results = searchListings("emptynullalephOnelament")
    assert results == []

  def testPriceFilterExcludesOverBudget(self):
    results = searchListings("shirt", maxPrice=25.00)
    assert all(r["price"] <= 25.00 for r in results)

  def testPriceFilterNoneIncludesAllPrices(self):
    withFilter = searchListings("vintage", maxPrice=30.00)
    withoutFilter = searchListings("vintage")
    assert len(withoutFilter) >= len(withFilter)

  def testSizeFilterTokensMatch(self):
    results = searchListings("jacket", size="S")
    for r in results:
      tokens = re.findall(r'\w+', r["size"].lower())
      assert "s" in tokens

  def testSizeFilterCaseInsensitive(self):
    lower = searchListings("top", size="m")
    upper = searchListings("top", size="M")
    assert lower == upper

  def testSizeFilterReducesResults(self):
    allResults = searchListings("vintage")
    filtered = searchListings("vintage", size="XL")
    assert len(filtered) <= len(allResults)

  def testCombinedSizeAndPriceFilter(self):
    results = searchListings("top", size="M", maxPrice=50.00)
    for r in results:
      assert r["price"] <= 50.00
      tokens = re.findall(r'\w+', r["size"].lower())
      assert "m" in tokens

  def testResultsAreSortedBestMatchFirst(self):
    results = searchListings("vintage graphic tee streetwear")
    keywords = {"vintage", "graphic", "tee", "streetwear"}
    def score(listing):
      text = " ".join([
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        listing.get("brand", "") or "",
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
      ]).lower()

      return len(keywords & set(re.findall(r'\w+', text)))

    scores = [score(r) for r in results]
    assert scores == sorted(scores, reverse=True)

  def testEachResultIsADictWithExpectedKeys(self):
    results = searchListings("jacket")
    required = {"id", "title", "price", "size", "category", "platform"}
    for r in results: assert required.issubset(r.keys())


class TestSuggestOutfit:
  def testReturnsNonemptyStringWithWardrobe(self, mockGroq):
    result = suggestOutfit(SAMPLE_ITEM, POPULATED_WARDROBE)
    assert isinstance(result, str) and len(result) > 0

  def testReturnsNonemptyStringWithEmptyWardrobe(self, mockGroq):
    result = suggestOutfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str) and len(result) > 0

  def testPromptIncludesItemTitle(self, mockGroq):
    suggestOutfit(SAMPLE_ITEM, POPULATED_WARDROBE)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert SAMPLE_ITEM["title"] in prompt

  def testPromptIncludesItemColors(self, mockGroq):
    suggestOutfit(SAMPLE_ITEM, POPULATED_WARDROBE)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert any(color in prompt for color in SAMPLE_ITEM["colors"])

  def testEmptyWardrobePromptIsGeneralStyling(self, mockGroq):
    suggestOutfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    # Should mention new user / no wardrobe, not list specific wardrobe pieces
    assert "new user" in prompt or "don't have a wardrobe" in prompt.lower() or "wardrobe on file" in prompt

  def testPopulatedWardrobePromptIncludesWardrobeItems(self, mockGroq):
    suggestOutfit(SAMPLE_ITEM, POPULATED_WARDROBE)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "White Oversized Tee" in prompt
    assert "Black Skinny Jeans" in prompt

  def testGroqCalledExactlyOnce(self, mockGroq):
    suggestOutfit(SAMPLE_ITEM, POPULATED_WARDROBE)
    assert mockGroq.chat.completions.create.call_count == 1

  def testWardrobeMissingItemsKeyTreatedAsEmpty(self, mockGroq):
    result = suggestOutfit(SAMPLE_ITEM, {})
    assert isinstance(result, str) and len(result) > 0


class TestCreateFitCard:
  def testReturnsNonemptyStringForValidInput(self, mockGroq):
    result = createFitCard("Outfit: jeans and a white tee", SAMPLE_ITEM)
    assert isinstance(result, str) and len(result) > 0

  def testEmptyOutfitReturnsErrorString(self):
    result = createFitCard("", SAMPLE_ITEM)
    assert "couldn't generate" in result.lower()

  def testWhitespaceOutfitReturnsErrorString(self):
    result = createFitCard("   ", SAMPLE_ITEM)
    assert "couldn't generate" in result.lower()

  def testEmptyOutfitDoesNotCallGroq(self):
    with patch("tools._getGroqClient") as mockFactory:
      createFitCard("", SAMPLE_ITEM)
    mockFactory.assert_not_called()

  def testPromptIncludesItemTitle(self, mockGroq):
    createFitCard("Casual daytime look", SAMPLE_ITEM)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert SAMPLE_ITEM["title"] in prompt

  def testPromptIncludesFormattedPrice(self, mockGroq):
    createFitCard("Casual daytime look", SAMPLE_ITEM)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert f"${SAMPLE_ITEM['price']:.2f}" in prompt

  def testPromptIncludesPlatform(self, mockGroq):
    createFitCard("Casual daytime look", SAMPLE_ITEM)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert SAMPLE_ITEM["platform"] in prompt

  def testPromptIncludesOutfitText(self, mockGroq):
    outfit = "Pair with black jeans and chunky sneakers"
    createFitCard(outfit, SAMPLE_ITEM)
    prompt = mockGroq.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert outfit in prompt

  def testGroqCalledExactlyOnce(self, mockGroq):
    createFitCard("Weekend outfit", SAMPLE_ITEM)
    assert mockGroq.chat.completions.create.call_count == 1