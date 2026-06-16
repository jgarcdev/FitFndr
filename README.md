# FitFindr - Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template - fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code - organize it however makes sense for your design.

---

## Tool Inventory

### `searchListings(description, size, maxPrice)`

| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Item description |
| `size` | `str \| None` | Size string to filter by, or `None` to skip |
| `maxPrice` | `float \| None` | Maximum price inclusive, or `None` to skip |

**Returns:** `list[dict]` - matching listing dicts sorted by keyword relevance (best match first); empty list if nothing matches.

**Purpose:** Filters the listings by price and size, then ranks selected listings by keyword overlap between the description and each listing's title, description, category, brand, style tags, and colors. Stop words (`a`, `the`, `in`, etc.) are stripped before scoring so they don't inflate scores.

---

### `suggestOutfit(newItem, wardrobe)`

| Parameter | Type | Description |
|---|---|---|
| `newItem` | `dict` | A listing, the item the user is considering buying |
| `wardrobe` | `dict` | Wardrobe dict with an `"items"` key (may be empty) |

**Returns:** `str` - outfit suggestion text. If the wardrobe is empty, returns general styling advice instead of wardrobe-specific pairings.

**Purpose:** Sends a styled prompt to the LLM asking it to act as a personal stylist. When a wardrobe exists, the prompt lists all wardrobe items by name, category, colors, and style tags, and asks for 1-2 specific outfit combinations using named pieces. When the wardrobe is empty, it asks for general styling advice instead.

---

### `createFitCard(outfit, newItem)`

| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string returned by `suggestOutfit()` |
| `newItem` | `dict` | The listing dict for the thrifted item |

**Returns:** `str` - a 2-4 sentence caption with 3-5 hashtags. Returns an error message string (does not raise) if `outfit` is empty.

**Purpose:** Sends a prompt to the LLM asking it to write a casual Instagram/TikTok-style outfit-of-the-day caption. The prompt instructs the model to mention the item name, price, and platform exactly once each, end with hashtags, and avoid brand-voice language.

---

## How the Planning Loop Works

The loops runs sequentially and short-circuits on failure with later steps only execute if the earlier ones succeeded.

```
query string
    │
    ▼
1. Parse query with regex
   ├─ Extract maxPrice  →  "under $30", "$40", "max $50", "less than $25", "below $60"
   ├─ Extract size      →  "size M", "XL", "US 8", "W30 L32", etc.
   └─ Strip those tokens from the query to form a clean description
    │
    ▼
2. searchListings(description, size, maxPrice)
   │
   ├─ results == []  →  build a hint message ("try raising price limit" / "remove size filter" /
   │                    "try broader keywords"), set session["error"], RETURN early
   │
   └─ results non-empty  →  session["selected_item"] = results[0]
    │
    ▼
3. suggestOutfit(selected_item, wardrobe)
   │
   └─ session["outfit_suggestion"] = LLM response
    │
    ▼
4. createFitCard(outfit_suggestion, selected_item)
   │
   └─ session["fit_card"] = LLM caption
    │
    ▼
5. Return completed session dict
```

The only explicit branch is after step 2: if `searchListings` returns an empty list, the agent sets `error` and returns immediately, and `suggestOutfit` and `createFitCard` are never called. All other steps run unconditionally once search succeeds.

---

## State Management

All state for a single run is held in a session dictionary created by `_newSession()` with each call to `runAgent` being fresh.

| Key | Type | Set when | Passed to |
|---|---|---|---|
| `query` | `str` | Immediately (input) | Used in error messages |
| `parsed` | `dict` | After regex parsing | Logged; feeds `search_results` indirectly |
| `search_results` | `list[dict]` | After `searchListings` | Used to derive `selected_item` |
| `selected_item` | `dict \| None` | After non-empty search | `suggestOutfit`, `createFitCard`, UI formatter |
| `wardrobe` | `dict` | Immediately (input) | Passed directly to `suggestOutfit` |
| `outfit_suggestion` | `str \| None` | After `suggestOutfit` | Passed directly to `createFitCard` |
| `fit_card` | `str \| None` | After `createFitCard` | Returned to UI |
| `error` | `str \| None` | On early termination | Checked by UI before rendering |

The session dict is returned to Gradio, which checks `session["error"]` first. On error, only the first output panel shows the message; the other two panels receive empty strings.

---

## Error Handling

### `searchListings`
Never raises - returns an empty list on no match. The planning loop detects the empty list and builds a context-aware hint:
- If a price filter was active: "raise your price limit"
- If a size filter was active: "remove the size filter"
- Always appends: "try broader style keywords"

**Example:** Query `"designer ballgown size XXS under $5"` returns no results. The agent sets `session["error"] = 'No listings found for "designer ballgown size XXS under $5".\nTry: raise your price limit, remove the size filter, try broader style keywords.'`

### `suggestOutfit`
Handles an empty wardrobe gracefully - switches to a general styling prompt instead of raising. A missing `GROQ_API_KEY` raises `ValueError` with a message pointing to the `.env` file. Groq API errors propagate as-is (network issues, rate limits).

**Example:** Calling with `wardrobe=getEmptyWardrobe()` still returns a useful response like *"Pair this with high-waisted jeans and chunky sneakers for a 90s streetwear look."* rather than failing.

### `createFitCard`
Guards against an empty `outfit` string before calling the API - returns the string `"Couldn't generate a fit card - outfit details are missing. Try searching for an item first."` without raising. All other Groq errors propagate.

---

## Reflection

One way the planning helped is providing some form of structure 
that I can roughly follow, guiding me on what I need to think about as I write. However, it diverged when it got to the loop, 
as well as the contextual flow between the tools.
As I was writing and analyzing, I found a much easier and faster way to implement 
the agent.

---

## AI Usage


Instance 1: I asked the agent on how to extract the details needed from the user query, such as sizing and price, which it then provided the regex. I adapted it to the context and made sure the regex was working as intended.

Instance 2: I directed the agent to create a layout for testing the tool functions using pytest.
I then filled out the rest, adding the tests I wanted, while asking for specific how-to questions such as getting the prompt.