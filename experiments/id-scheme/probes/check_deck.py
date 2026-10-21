"""Structural sanity check for the review deck.

Counts animation hooks, slides and components so a broken edit is caught
before the deck is opened in a browser.
"""

from pathlib import Path

DECK = Path(__file__).resolve().parents[3] / "docs" / "snapshot-identity-review.html"


def main() -> None:
    text = DECK.read_text(encoding="utf-8")
    tokens = {
        "slides": '<section class="slide',
        "dark": "slide dark",
        "room": 'class="room',
        "tables": "<table",
        "a-up": "a-up",
        "a-fade": "a-fade",
        "counters": "data-count",
        "headline-lines": 'class="l"',
        "notes": "data-note=",
    }
    for name, token in tokens.items():
        print(f"{name:>16}: {text.count(token)}")
    print(f"{'bytes':>16}: {len(text.encode('utf-8'))}")


if __name__ == "__main__":
    main()
