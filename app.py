"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
  python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import runAgent
from utils.dataLoader import getExampleWardrobe, getEmptyWardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handleQuery(userQuery: str, wardrobeChoice: str) -> tuple[str, str, str]:
  """
  Called by Gradio when the user submits a query.

  Args:
      user_query:     The text the user typed into the search box.
      wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

  Returns:
      A tuple of three strings:
          (listing_text, outfit_suggestion, fit_card)
      Each string maps to one of the three output panels in the UI.

  TODO:
      1. Guard against an empty query (return early with an error message).
      2. Select the wardrobe based on wardrobe_choice.
      3. Call run_agent() with the query and selected wardrobe.
      4. If session["error"] is set, return the error in the first panel
          and empty strings for the other two.
      5. Otherwise, format session["selected_item"] into a readable listing_text
          string and return it along with session["outfit_suggestion"] and
          session["fit_card"].
  """
  if not userQuery or not userQuery.strip(): return "Please enter a search query.", "", ""

  wardrobe = getExampleWardrobe() if wardrobeChoice == "Example wardrobe" else getEmptyWardrobe()

  session = runAgent(query=userQuery.strip(), wardrobe=wardrobe)

  if session["error"]: return session["error"], "", ""

  item = session["selected_item"]
  colors = ", ".join(item.get("colors") or [])
  tags = ", ".join(item.get("style_tags") or [])
  brand = f"Brand: {item['brand']}\n" if item.get("brand") else ""
  listingText = (
    f"{item['title']}\n"
    f"Price: ${item['price']:.2f} on {item['platform'].capitalize()}\n"
    f"Size: {item['size']}  |  Condition: {item['condition']}\n"
    f"{brand}"
    f"Colors: {colors}\n"
    f"Style: {tags}\n\n"
    f"{item['description']}"
  )

  return listingText, session["outfit_suggestion"], session["fit_card"]


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
  "vintage graphic tee under $30",
  "90s track jacket in size M",
  "flowy midi skirt under $40",
  "black combat boots size 8",
  "designer ballgown size XXS under $5" # deliberate no-results test
]

def buildInterface():
  with gr.Blocks(title="FitFindr") as demo:
    gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
    """)

    with gr.Row():
      queryInput = gr.Textbox(label="What are you looking for?", placeholder="e.g. vintage graphic tee under $30, size M", lines=2, scale=3)
      wardrobeChoice = gr.Radio(choices=["Example wardrobe", "Empty wardrobe (new user)"], value="Example wardrobe", label="Wardrobe", scale=1)

    submitBtn = gr.Button("Find it", variant="primary")

    with gr.Row():
      listing_output = gr.Textbox(label="🛍️ Top listing found", lines=8, interactive=False)
      outfit_output = gr.Textbox(label="👗 Outfit idea", lines=8, interactive=False)
      fitcard_output = gr.Textbox(label="✨ Your fit card", lines=8, interactive=False)

    gr.Examples(examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES], inputs=[queryInput, wardrobeChoice], label="Try these queries")

    submitBtn.click(fn=handleQuery, inputs=[queryInput, wardrobeChoice], outputs=[listing_output, outfit_output, fitcard_output])
    queryInput.submit(fn=handleQuery, inputs=[queryInput, wardrobeChoice], outputs=[listing_output, outfit_output, fitcard_output])

  return demo


if __name__ == "__main__":
  demo = buildInterface()
  demo.launch()