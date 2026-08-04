from __future__ import annotations

__author__ = "TheHolyOneZ"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026 TheHolyOneZ"
__version__ = "1.0.0"

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.align import Align
from rich.box import ROUNDED
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Static

BRAND = "TheHolyOneZ"
APP_NAME = "ZTYPE"
TAGLINE = "terminal typing trainer"

LOGO = r"""
███████╗ ████████╗ ██╗   ██╗ ██████╗  ███████╗
╚══███╔╝ ╚══██╔══╝ ╚██╗ ██╔╝ ██╔══██╗ ██╔════╝
  ███╔╝     ██║     ╚████╔╝  ██████╔╝ █████╗
 ███╔╝      ██║      ╚██╔╝   ██╔═══╝  ██╔══╝
███████╗    ██║       ██║    ██║      ███████╗
╚══════╝    ╚═╝       ╚═╝    ╚═╝      ╚══════╝
""".strip("\n").split("\n")
LOGO_WIDTH = max(len(line) for line in LOGO)

CORAL = "#d97757"
CREAM = "#e6e0d6"
MUTED = "#7a736a"
FAINT = "#4a4540"
LINE = "#2e2b28"
GREEN = "#8fbf7a"
RED = "#e06c75"
RED_BG = "#3b1f21"
PAPER = "#161513"
PANEL = "#1b1a18"
SELECT = "#26241f"

LOGO_SHADES = ["#f0a07a", "#e8895f", "#e07f57", "#d97757", "#c66a4c", "#b25c42"]
LOGO_SHADOW = "#5c3427"

MT_ROOT = "https://raw.githubusercontent.com/monkeytypegame/monkeytype/master/frontend/static"
QUOTES_URL = f"{MT_ROOT}/quotes/english.json"
WORDS_URL = MT_ROOT + "/languages/{name}.json"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ztype"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ztype"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SEEN_FILE = CACHE_DIR / "seen.json"

QUOTE_GROUPS = {
    "short": (0, 100),
    "medium": (101, 300),
    "long": (301, 600),
    "any": (0, 600),
}

WORD_POOLS = ["english", "english_1k", "english_5k", "english_10k"]

FALLBACK_WORDS = """
the be of and a to in he have it that for they with as not on she at by this
we you do but from or which one would all will there say who make when can
more if no man out other so what time up go about than into could state only
new year some take come these know see use get like then first any work now
may such give over think most even find day also after way many must look
before great back through long where much should well people down own just
because good each those feel seem how high too place little world very still
nation hand old life tell write become here show house both between need mean
call develop under last right move thing general school never same another
begin while number part turn real leave might want point form off child few
small since against ask late home interest large person end open public follow
during present without again hold govern around possible head consider word
program problem however lead system set order eye plan run keep face fact
group play stand increase early course change help line
""".split()

BUILTIN_PASSAGES = [
    "The best way to predict the future is to invent it. Every great tool "
    "began as a small idea that somebody refused to abandon, and every "
    "finished thing you admire was once a rough sketch that only its maker "
    "could see.",
    "Simplicity is the ultimate sophistication. When you strip a design down "
    "to what it truly needs, the remaining parts start to feel inevitable, "
    "as though the object could not have been shaped any other way.",
    "A program is a letter written to another person, and only incidentally "
    "an instruction for a machine. Write it so that the next reader, who may "
    "well be you, can follow the argument without a map.",
    "Typing quickly is less about moving fast and more about moving without "
    "hesitation. The keys are always in the same place; what changes is how "
    "much of your attention the act of finding them still demands.",
    "Terminals have outlived nearly every interface that promised to replace "
    "them. They are small, honest windows into a machine, and with a little "
    "colour and care they can be beautiful as well as fast.",
    "Practice does not make perfect, it makes permanent. Slow down until the "
    "motion is correct, then let speed arrive on its own, quietly, the way "
    "it always does when you stop chasing it.",
    "Good software feels like a well made hand tool. It sits comfortably, "
    "does one thing without complaint, and leaves you free to think about "
    "the work rather than about the tool itself.",
    "The river does not hurry, yet everything is accomplished. Steady "
    "attention, repeated daily, moves further than any burst of enthusiasm "
    "that burns brightly for an afternoon and then goes out.",
]


@dataclass
class Settings:
    mode: str = "words"
    word_pool: str = "english_1k"
    word_count: int = 25
    quote_length: str = "medium"
    punctuation: bool = False
    numbers: bool = False
    online: bool = True

    @classmethod
    def load(cls) -> "Settings":
        try:
            raw = json.loads(SETTINGS_FILE.read_text())
        except (OSError, ValueError):
            return cls()
        known = {f: raw[f] for f in cls.__dataclass_fields__ if f in raw}
        try:
            return cls(**known)
        except TypeError:
            return cls()

    def save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2))
        except OSError:
            pass

    def summary(self) -> str:
        if self.mode == "words":
            bits = [f"{self.word_count} words", self.word_pool.replace("english", "en")]
            if self.punctuation:
                bits.append("punctuation")
            if self.numbers:
                bits.append("numbers")
            return " · ".join(bits)
        if self.mode == "quote":
            return f"quotes · {self.quote_length}"
        return "curated passages"


@dataclass
class Choice:
    key: str
    label: str
    values: list
    labels: list[str]
    help: str
    only_for: str | None = None

    def index_of(self, value) -> int:
        try:
            return self.values.index(value)
        except ValueError:
            return 0


CHOICES = [
    Choice("mode", "mode", ["words", "quote", "passage"],
           ["random words", "real quotes", "curated passages"],
           "what gets generated for each run"),
    Choice("word_count", "length", [10, 25, 50, 100],
           ["10 words", "25 words", "50 words", "100 words"],
           "how much text you have to get through", only_for="words"),
    Choice("word_pool", "word pool", WORD_POOLS,
           ["top 200", "top 1k", "top 5k", "top 10k"],
           "bigger pools mean rarer, harder words", only_for="words"),
    Choice("punctuation", "punctuation", [False, True], ["off", "on"],
           "sprinkle in commas, capitals and full stops", only_for="words"),
    Choice("numbers", "numbers", [False, True], ["off", "on"],
           "mix digits into the word stream", only_for="words"),
    Choice("quote_length", "quote size", ["short", "medium", "long", "any"],
           ["short", "medium", "long", "any"],
           "which of Monkeytype's length buckets to draw from",
           only_for="quote"),
    Choice("online", "text source", [True, False],
           ["online library", "offline built-ins"],
           "fetch from the Monkeytype dataset, or stay local"),
]


class Library:
    def __init__(self) -> None:
        self.quotes: list[dict] = []
        self.words: dict[str, list[str]] = {}
        self.status: str = "loading"
        self._bags: dict[str, list[int]] = {}
        self._seen: dict[str, set] = {"quote": set(), "passage": set()}
        self._load_seen()

    def _cache_path(self, name: str) -> Path:
        return CACHE_DIR / f"{name}.json"

    def _read_cache(self, name: str):
        try:
            return json.loads(self._cache_path(name).read_text())
        except (OSError, ValueError):
            return None

    def _write_cache(self, name: str, payload: str) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._cache_path(name).write_text(payload)
        except OSError:
            pass

    def _load_seen(self) -> None:
        try:
            raw = json.loads(SEEN_FILE.read_text())
            for key in ("quote", "passage"):
                self._seen[key] = set(raw.get(key, []))
        except (OSError, ValueError):
            pass

    def _save_seen(self) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            SEEN_FILE.write_text(
                json.dumps({k: sorted(v) for k, v in self._seen.items()})
            )
        except OSError:
            pass

    def load_cached(self) -> None:
        data = self._read_cache("quotes_english")
        if isinstance(data, dict) and data.get("quotes"):
            self.quotes = data["quotes"]
        for pool in WORD_POOLS:
            data = self._read_cache(pool)
            if isinstance(data, dict) and data.get("words"):
                self.words[pool] = data["words"]
        self.status = self._describe()

    def sync(self, settings: Settings) -> bool:
        if not settings.online:
            self.status = "offline by choice"
            return True

        wanted: list[tuple[str, str]] = []
        if not self.quotes:
            wanted.append(("quotes_english", QUOTES_URL))
        pool = settings.word_pool
        if pool not in self.words:
            wanted.append((pool, WORDS_URL.format(name=pool)))
        if not wanted:
            self.status = self._describe()
            return True

        self.status = "fetching library…"
        ok = False
        for name, url in wanted:
            payload = self._download(url)
            if payload is None:
                continue
            try:
                data = json.loads(payload)
            except ValueError:
                continue
            if name == "quotes_english" and data.get("quotes"):
                self.quotes = data["quotes"]
                ok = True
            elif data.get("words"):
                self.words[name] = data["words"]
                ok = True
            else:
                continue
            self._write_cache(name, payload)

        self.status = self._describe() if ok else self._describe(failed=True)
        return True

    @staticmethod
    def _download(url: str) -> str | None:
        request = urllib.request.Request(url, headers={"User-Agent": "ztype"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return None

    def _describe(self, failed: bool = False) -> str:
        if not self.quotes and not self.words:
            return "offline — using built-ins" if failed else "built-ins only"
        bits = []
        if self.quotes:
            bits.append(f"{len(self.quotes):,} quotes")
        if self.words:
            biggest = max(len(w) for w in self.words.values())
            bits.append(f"{biggest:,} words")
        tail = " (offline)" if failed else ""
        return " · ".join(bits) + tail

    def _draw_unseen(self, kind: str, pool: list, key) -> object:
        if not pool:
            return None
        seen = self._seen.setdefault(kind, set())
        fresh = [item for item in pool if key(item) not in seen]
        if not fresh:
            seen.clear()
            fresh = pool
        item = random.choice(fresh)
        seen.add(key(item))
        self._save_seen()
        return item

    def make_text(self, settings: Settings) -> tuple[str, str]:
        if settings.mode == "quote":
            return self._make_quote(settings)
        if settings.mode == "passage":
            text = self._draw_unseen("passage", BUILTIN_PASSAGES, lambda p: p[:40])
            return text or BUILTIN_PASSAGES[0], "curated"
        return self._make_words(settings)

    def _make_quote(self, settings: Settings) -> tuple[str, str]:
        low, high = QUOTE_GROUPS.get(settings.quote_length, QUOTE_GROUPS["any"])
        pool = [q for q in self.quotes if low <= q.get("length", 0) <= high]
        quote = self._draw_unseen("quote", pool, lambda q: q["id"]) if pool else None
        if quote is None:
            text = self._draw_unseen("passage", BUILTIN_PASSAGES, lambda p: p[:40])
            return text or BUILTIN_PASSAGES[0], "built-in (no quotes cached)"
        clean = " ".join(str(quote["text"]).split())
        return clean, f"— {quote.get('source', 'unknown')}"

    def _make_words(self, settings: Settings) -> tuple[str, str]:
        pool = self.words.get(settings.word_pool) or FALLBACK_WORDS
        words = [random.choice(pool) for _ in range(settings.word_count)]
        if settings.numbers:
            words = self._sprinkle_numbers(words)
        if settings.punctuation:
            words = self._punctuate(words)
        label = settings.word_pool.replace("english", "en")
        if pool is FALLBACK_WORDS:
            label = "built-in words"
        return " ".join(words), label

    @staticmethod
    def _sprinkle_numbers(words: list[str]) -> list[str]:
        out = list(words)
        for index in range(len(out)):
            if random.random() < 0.12:
                out[index] = str(random.randint(0, 999))
        return out

    @staticmethod
    def _punctuate(words: list[str]) -> list[str]:
        out: list[str] = []
        capitalise = True
        last = len(words) - 1
        for index, word in enumerate(words):
            if capitalise:
                word = word.capitalize()
                capitalise = False
            roll = random.random()
            if index < last:
                if roll < 0.08:
                    word += random.choice(",,;:")
                elif roll < 0.14:
                    word += random.choice("...?!")
                    capitalise = True
                elif roll < 0.17:
                    word = f"({word})"
                elif roll < 0.20:
                    word = f'"{word}"'
            out.append(word)
        if out and out[-1][-1] not in ".?!":
            out[-1] += "."
        return out


class Logo(Widget):
    def render(self) -> RenderableType:
        if self.size.width < LOGO_WIDTH + 2:
            small = Text(justify="center")
            small.append("✻ ", style=f"bold {CORAL}")
            small.append(APP_NAME, style=f"bold {CREAM}")
            return small
        art = Text(no_wrap=True, overflow="crop")
        for index, line in enumerate(LOGO):
            shade = LOGO_SHADES[index % len(LOGO_SHADES)]
            for char in line.ljust(LOGO_WIDTH):
                art.append(char, style=shade if char == "█" else LOGO_SHADOW)
            if index < len(LOGO) - 1:
                art.append("\n")
        return art


class MenuOption(Widget):
    selected: reactive[bool] = reactive(False)

    def __init__(self, key: str, label: str, blurb: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.key = key
        self.label = label
        self.blurb = blurb

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")

    def render(self) -> RenderableType:
        row = Text(no_wrap=True, overflow="crop")
        row.append("  ▸ " if self.selected else "    ", style=CORAL)
        row.append(
            self.label,
            style=f"bold {CREAM}" if self.selected else CREAM,
        )
        pad = self.size.width - len(self.label) - len(self.blurb) - 8
        row.append(" " * max(pad, 2), style=MUTED)
        row.append(self.blurb, style=MUTED if self.selected else FAINT)
        row.append("  ")
        return row

    def on_enter(self, event: events.Enter) -> None:
        self.post_message(MenuHover(self))

    def on_click(self, event: events.Click) -> None:
        self.post_message(MenuChosen(self.key))


class MenuHover(Message):
    def __init__(self, option: MenuOption) -> None:
        super().__init__()
        self.option = option


class MenuChosen(Message):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class ChoiceRow(Widget):
    selected: reactive[bool] = reactive(False)
    relevant: reactive[bool] = reactive(True)

    def __init__(self, choice: Choice, **kwargs) -> None:
        super().__init__(**kwargs)
        self.choice = choice
        self.value_label = ""

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")

    def render(self) -> RenderableType:
        dim = not self.relevant
        row = Text(no_wrap=True, overflow="crop")
        row.append("  ▸ " if self.selected else "    ", style=CORAL)
        label_style = FAINT if dim else (f"bold {CREAM}" if self.selected else CREAM)
        row.append(self.choice.label, style=label_style)

        value = f"‹ {self.value_label} ›" if self.selected and not dim else f"  {self.value_label}  "
        pad = self.size.width - len(self.choice.label) - len(value) - 6
        row.append(" " * max(pad, 2))
        if dim:
            row.append(value, style=FAINT)
        else:
            row.append(value, style=f"bold {CORAL}" if self.selected else MUTED)
        row.append("  ")
        return row

    def on_enter(self, event: events.Enter) -> None:
        self.post_message(RowHover(self))

    def on_click(self, event: events.Click) -> None:
        self.post_message(RowCycle(self, 1))


class RowHover(Message):
    def __init__(self, row: ChoiceRow) -> None:
        super().__init__()
        self.row = row


class RowCycle(Message):
    def __init__(self, row: ChoiceRow, step: int) -> None:
        super().__init__()
        self.row = row
        self.step = step


class TypingBoard(Widget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.target: str = ""
        self.typed: list[str] = []

    def render(self) -> RenderableType:
        text = Text(justify="left")
        typed_len = len(self.typed)

        for index, expected in enumerate(self.target):
            if index < typed_len:
                got = self.typed[index]
                if got == expected:
                    text.append(expected, style=GREEN)
                elif expected == " ":
                    text.append(" ", style=f"{RED} on {RED_BG}")
                else:
                    text.append(expected, style=f"bold {RED}")
            elif index == typed_len:
                text.append(expected, style=f"bold {PAPER} on {CORAL}")
            else:
                text.append(expected, style=MUTED)

        if typed_len >= len(self.target):
            text.append(" ", style=f"on {CORAL}")
        return text


class ProgressLine(Widget):
    progress: reactive[float] = reactive(0.0)

    def render(self) -> RenderableType:
        width = max(self.size.width - 5, 10)
        filled = round(width * self.progress)
        bar = Text(no_wrap=True, overflow="crop")
        bar.append("━" * filled, style=CORAL)
        bar.append("━" * (width - filled), style=LINE)
        bar.append(f"{self.progress * 100:4.0f}%", style=MUTED)
        return bar

    def on_resize(self, event: events.Resize) -> None:
        self.refresh()


class StatCard(Widget):
    value: reactive[str] = reactive("--")

    def __init__(self, label: str, suffix: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.suffix = suffix

    def render(self) -> RenderableType:
        text = Text(no_wrap=True, overflow="crop")
        text.append(self.label.upper(), style=MUTED)
        text.append("\n")
        text.append(self.value, style=f"bold {CORAL}")
        if self.suffix:
            text.append(self.suffix, style=MUTED)
        return text


def rating_for(wpm: float) -> str:
    for threshold, word in (
        (25, "warming up"),
        (40, "steady"),
        (60, "quick"),
        (80, "fast"),
        (100, "very fast"),
    ):
        if wpm < threshold:
            return word
    return "extraordinary"


class ResultsView(Widget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.stats: dict[str, object] = {}
        self.source: str = ""

    def render(self) -> RenderableType:
        stats = self.stats
        if not stats:
            return Text("")

        wpm = float(stats["wpm"])

        headline = Text(justify="center")
        headline.append(f"{wpm:.0f}", style=f"bold {CORAL}")
        headline.append("  wpm", style=MUTED)

        table = Table.grid(padding=(0, 3))
        table.add_column(justify="right", style=MUTED)
        table.add_column(justify="left", style=f"bold {CREAM}")
        table.add_row("accuracy", f"{stats['accuracy']:.1f} %")
        table.add_row("raw", f"{stats['raw_wpm']:.0f} wpm")
        table.add_row(
            "errors",
            f"{stats['mistakes']}  ({stats['uncorrected']} left uncorrected)",
        )
        table.add_row("time", f"{stats['elapsed']:.1f} s")
        table.add_row("characters", f"{stats['correct']} / {stats['keystrokes']}")
        if self.source:
            table.add_row("text", self.source)

        footer = Text(justify="center")
        for key, caption in (("R", "again"), ("M", "menu"), ("Q", "quit")):
            if footer.plain:
                footer.append("     ", style=MUTED)
            footer.append(key, style=f"bold {CORAL}")
            footer.append(f" {caption}", style=MUTED)

        body = Group(headline, Text(""), Align.center(table), Text(""), footer)
        return Panel(
            body,
            box=ROUNDED,
            border_style=CORAL,
            title=f"[{CORAL}]✻[/] [{CREAM}]results[/]",
            title_align="left",
            subtitle=f"[{MUTED}]{rating_for(wpm)}[/]",
            subtitle_align="right",
            padding=(1, 2),
            style=f"on {PANEL}",
        )


def topbar(right_text: str) -> tuple[Text, Text]:
    left = Text()
    left.append("✻ ", style=f"bold {CORAL}")
    left.append(APP_NAME.lower(), style=f"bold {CREAM}")
    left.append("  ·  ", style=LINE)
    left.append(f"by {BRAND}", style=MUTED)

    right = Text(justify="right")
    right.append(right_text, style=FAINT)
    return left, right


class MenuScreen(Screen):
    ITEMS = [
        ("start", "start typing", "the clock starts on your first keystroke"),
        ("settings", "settings", "what gets generated, and how long"),
        ("quit", "quit", "see you next time"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            yield Logo(id="logo")
            yield Static(id="tagline")
            with Vertical(id="menu"):
                for key, label, blurb in self.ITEMS:
                    yield MenuOption(key, label, blurb, classes="menu-option")
            yield Static(id="config-line")
            yield Static(id="library-line")
            yield Static(id="hint")

    def on_mount(self) -> None:
        tagline = Text(justify="center")
        tagline.append(TAGLINE, style=MUTED)
        self.query_one("#tagline", Static).update(tagline)

        hint = Text(justify="center")
        for key, caption in (("↑↓", "move"), ("enter", "select"),
                             ("s", "settings"), ("q", "quit")):
            if hint.plain:
                hint.append("  ·  ", style=LINE)
            hint.append(key, style=CORAL)
            hint.append(f" {caption}", style=FAINT)
        self.query_one("#hint", Static).update(hint)

        self.refresh_rows()
        self.refresh_status()

    def refresh_rows(self) -> None:
        for position, option in enumerate(self.query(MenuOption)):
            option.selected = position == self.index

    def refresh_status(self) -> None:
        settings = self.app.settings

        config = Text(justify="center")
        config.append("▸ ", style=FAINT)
        config.append(settings.summary(), style=CREAM)
        self.query_one("#config-line", Static).update(config)

        library = Text(justify="center")
        library.append("library ", style=FAINT)
        library.append(self.app.library.status, style=MUTED)
        self.query_one("#library-line", Static).update(library)

    def move(self, step: int) -> None:
        self.index = (self.index + step) % len(self.ITEMS)
        self.refresh_rows()

    def activate(self, key: str) -> None:
        if key == "start":
            self.app.push_screen(TypeScreen())
        elif key == "settings":
            self.app.push_screen(SettingsScreen())
        elif key == "quit":
            self.app.exit()

    def on_screen_resume(self, event: events.ScreenResume) -> None:
        self.refresh_status()

    def on_menu_hover(self, message: MenuHover) -> None:
        keys = [item[0] for item in self.ITEMS]
        self.index = keys.index(message.option.key)
        self.refresh_rows()

    def on_menu_chosen(self, message: MenuChosen) -> None:
        self.activate(message.key)

    def on_key(self, event: events.Key) -> None:
        key = event.key
        letter = (event.character or "").lower()
        if key in ("up", "k") or (key == "shift+tab"):
            self.move(-1)
        elif key in ("down", "j", "tab"):
            self.move(1)
        elif key in ("enter", "space"):
            self.activate(self.ITEMS[self.index][0])
        elif letter == "s":
            self.activate("settings")
        elif letter == "q" or key == "escape":
            self.app.exit()
        event.stop()
        event.prevent_default()


class SettingsScreen(Screen):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            with Horizontal(id="topbar"):
                yield Static(id="brand")
                yield Static(id="brand-right")
            with Vertical(id="options"):
                for choice in CHOICES:
                    yield ChoiceRow(choice, classes="choice-row")
            yield Static(id="help-line")
            yield Static(id="hint")

    def on_mount(self) -> None:
        left, right = topbar("settings")
        self.query_one("#brand", Static).update(left)
        self.query_one("#brand-right", Static).update(right)

        hint = Text(justify="center")
        for key, caption in (("↑↓", "row"), ("←→", "change"), ("esc", "back")):
            if hint.plain:
                hint.append("  ·  ", style=LINE)
            hint.append(key, style=CORAL)
            hint.append(f" {caption}", style=FAINT)
        self.query_one("#hint", Static).update(hint)
        self.refresh_rows()

    def refresh_rows(self) -> None:
        settings = self.app.settings
        rows = list(self.query(ChoiceRow))
        for position, row in enumerate(rows):
            choice = row.choice
            value = getattr(settings, choice.key)
            row.value_label = choice.labels[choice.index_of(value)]
            row.relevant = choice.only_for in (None, settings.mode)
            row.selected = position == self.index
            row.refresh()

        help_text = Text(justify="center")
        help_text.append(CHOICES[self.index].help, style=FAINT)
        self.query_one("#help-line", Static).update(help_text)

    def cycle(self, row: ChoiceRow, step: int) -> None:
        choice = row.choice
        settings = self.app.settings
        if choice.only_for not in (None, settings.mode):
            return
        current = choice.index_of(getattr(settings, choice.key))
        new_value = choice.values[(current + step) % len(choice.values)]
        setattr(settings, choice.key, new_value)
        settings.save()
        if choice.key in ("online", "word_pool", "mode"):
            self.app.sync_library()
        self.refresh_rows()

    def move(self, step: int) -> None:
        self.index = (self.index + step) % len(CHOICES)
        self.refresh_rows()

    def on_row_hover(self, message: RowHover) -> None:
        self.index = CHOICES.index(message.row.choice)
        self.refresh_rows()

    def on_row_cycle(self, message: RowCycle) -> None:
        self.index = CHOICES.index(message.row.choice)
        self.cycle(message.row, message.step)

    def on_key(self, event: events.Key) -> None:
        key = event.key
        rows = list(self.query(ChoiceRow))
        if key in ("up", "k", "shift+tab"):
            self.move(-1)
        elif key in ("down", "j", "tab"):
            self.move(1)
        elif key in ("left", "h"):
            self.cycle(rows[self.index], -1)
        elif key in ("right", "l", "enter", "space"):
            self.cycle(rows[self.index], 1)
        elif key in ("escape", "backspace") or (event.character or "").lower() == "q":
            self.dismiss()
        event.stop()
        event.prevent_default()


class TypeScreen(Screen):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.keystrokes = 0
        self.mistakes = 0
        self.source = ""
        self._hint_state: tuple[bool, bool] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            with Horizontal(id="topbar"):
                yield Static(id="brand")
                yield Static(id="brand-right")
            with Vertical(id="test-view"):
                yield TypingBoard(id="board")
                yield ProgressLine(id="progress")
                with Grid(id="stats"):
                    yield StatCard("wpm", id="wpm")
                    yield StatCard("accuracy", suffix=" %", id="accuracy")
                    yield StatCard("time", suffix=" s", id="time")
                    yield StatCard("errors", id="errors")
            yield ResultsView(id="results")
            yield Static(id="hint")

    def on_mount(self) -> None:
        left, right = topbar(self.app.settings.summary())
        self.query_one("#brand", Static).update(left)
        self.query_one("#brand-right", Static).update(right)
        self.new_round()
        self.set_interval(0.1, self.refresh_stats)

    @property
    def board(self) -> TypingBoard:
        return self.query_one("#board", TypingBoard)

    @property
    def finished(self) -> bool:
        return self.finished_at is not None

    def new_round(self) -> None:
        board = self.board
        board.target, self.source = self.app.library.make_text(self.app.settings)
        board.typed = []
        board.border_title = "the text"
        board.border_subtitle = self.source
        board.add_class("-idle")
        board.refresh()

        self.started_at = None
        self.finished_at = None
        self.keystrokes = 0
        self.mistakes = 0

        self.query_one("#test-view", Vertical).display = True
        self.query_one("#results", ResultsView).display = False
        self.query_one("#progress", ProgressLine).progress = 0.0
        self.refresh_stats()

    def finish_round(self) -> None:
        self.finished_at = time.monotonic()
        results = self.query_one("#results", ResultsView)
        results.stats = self.snapshot()
        results.source = self.source
        results.refresh()
        self.query_one("#test-view", Vertical).display = False
        results.display = True
        self.refresh_stats()

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return end - self.started_at

    @property
    def correct_chars(self) -> int:
        board = self.board
        return sum(1 for got, want in zip(board.typed, board.target) if got == want)

    def snapshot(self) -> dict[str, object]:
        elapsed = self.elapsed
        minutes = elapsed / 60
        correct = self.correct_chars
        settled = elapsed >= 0.3 and self.keystrokes > 0

        wpm = (correct / 5) / minutes if settled else 0.0
        raw_wpm = (self.keystrokes / 5) / minutes if settled else 0.0
        accuracy = (
            (self.keystrokes - self.mistakes) / self.keystrokes * 100
            if self.keystrokes
            else 100.0
        )
        board = self.board
        uncorrected = sum(
            1 for got, want in zip(board.typed, board.target) if got != want
        )
        return {
            "wpm": wpm,
            "raw_wpm": raw_wpm,
            "accuracy": accuracy,
            "elapsed": elapsed,
            "correct": correct,
            "keystrokes": self.keystrokes,
            "mistakes": self.mistakes,
            "uncorrected": uncorrected,
        }

    def refresh_stats(self) -> None:
        board = self.board
        stats = self.snapshot()
        started = self.started_at is not None

        self.query_one("#wpm", StatCard).value = (
            f"{stats['wpm']:.0f}" if started else "--"
        )
        self.query_one("#accuracy", StatCard).value = (
            f"{stats['accuracy']:.0f}" if started else "--"
        )
        self.query_one("#time", StatCard).value = (
            f"{stats['elapsed']:.1f}" if started else "--"
        )
        self.query_one("#errors", StatCard).value = str(stats["mistakes"])

        if board.target:
            self.query_one("#progress", ProgressLine).progress = min(
                len(board.typed) / len(board.target), 1.0
            )
        self.update_hint(started)

    def update_hint(self, started: bool) -> None:
        state = (self.finished, started)
        if state == self._hint_state:
            return
        self._hint_state = state

        hint = Text(justify="center")
        if self.finished:
            pairs = [("R", "again"), ("M", "menu"), ("Q", "quit")]
            hint.append("finished", style=GREEN)
            hint.append("  ·  ", style=LINE)
        else:
            pairs = [("tab", "new text"), ("esc", "menu"), ("ctrl+c", "quit")]
            hint.append(
                "type the first letter to start the clock" if not started
                else "keep going",
                style=MUTED,
            )
            hint.append("  ·  ", style=LINE)
        for position, (key, caption) in enumerate(pairs):
            if position:
                hint.append("  ·  ", style=LINE)
            hint.append(key, style=CORAL)
            hint.append(f" {caption}", style=FAINT)
        self.query_one("#hint", Static).update(hint)

    def on_key(self, event: events.Key) -> None:
        letter = (event.character or event.key).lower()

        if self.finished:
            if letter == "r":
                self.new_round()
            elif letter == "m" or event.key == "escape":
                self.dismiss()
            elif letter == "q":
                self.app.exit()
            event.stop()
            event.prevent_default()
            return

        if event.key == "escape":
            self.dismiss()
        elif event.key == "tab":
            self.new_round()
        elif event.key == "backspace":
            board = self.board
            if board.typed:
                board.typed.pop()
                board.refresh()
        elif event.is_printable and event.character is not None:
            self.type_character(event.character)

        event.stop()
        event.prevent_default()
        self.refresh_stats()

    def type_character(self, char: str) -> None:
        board = self.board
        index = len(board.typed)
        if index >= len(board.target):
            return

        if self.started_at is None:
            self.started_at = time.monotonic()
            board.remove_class("-idle")

        self.keystrokes += 1
        if char != board.target[index]:
            self.mistakes += 1

        board.typed.append(char)
        board.refresh()

        if len(board.typed) >= len(board.target):
            self.finish_round()


class ZTypeApp(App):
    ENABLE_COMMAND_PALETTE = False
    TITLE = f"{APP_NAME} · {BRAND}"

    CSS = f"""
    Screen {{
        background: {PAPER};
        align: center middle;
    }}

    #shell {{
        width: 100%;
        max-width: 96;
        height: auto;
        padding: 0 2;
    }}

    #topbar {{
        height: 1;
        margin-bottom: 1;
    }}
    #brand {{ width: 1fr; }}
    #brand-right {{ width: auto; }}

    #hint {{
        height: 1;
        margin-top: 1;
        text-align: center;
    }}

    #logo {{
        height: {len(LOGO)};
        margin-bottom: 1;
        text-align: center;
    }}

    #tagline {{
        height: 1;
        margin-bottom: 1;
        text-align: center;
    }}

    #menu {{
        height: auto;
        margin: 0 0 1 0;
    }}

    .menu-option {{
        height: 1;
        width: 100%;
    }}

    .menu-option.-selected {{
        background: {SELECT};
    }}

    #config-line, #library-line {{
        height: 1;
        text-align: center;
    }}

    #options {{
        height: auto;
        background: {PANEL};
        border: round {LINE};
        padding: 1 1;
    }}

    .choice-row {{
        height: 1;
        width: 100%;
    }}

    .choice-row.-selected {{
        background: {SELECT};
    }}

    #help-line {{
        height: 1;
        margin-top: 1;
        text-align: center;
    }}

    #test-view {{
        height: auto;
    }}

    #board {{
        height: auto;
        min-height: 5;
        background: {PANEL};
        border: round {CORAL};
        border-title-color: {CREAM};
        border-title-align: left;
        border-subtitle-color: {MUTED};
        border-subtitle-align: right;
        padding: 1 2;
    }}

    #board.-idle {{
        border: round {LINE};
    }}

    #progress {{
        height: 1;
        margin: 1 0;
    }}

    #stats {{
        height: 4;
        grid-size: 4 1;
        grid-gutter: 0 1;
    }}

    StatCard {{
        width: 100%;
        height: 100%;
        background: {PANEL};
        border: round {LINE};
        padding: 0 1;
    }}

    #results {{
        height: auto;
        display: none;
    }}
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.settings = Settings.load()
        self.library = Library()

    def on_mount(self) -> None:
        self.library.load_cached()
        self.push_screen(MenuScreen())
        self.sync_library()

    @work(thread=True, exclusive=True, group="library")
    def sync_library(self) -> None:
        self.library.sync(self.settings)
        self.call_from_thread(self.library_changed)

    def library_changed(self) -> None:
        for screen in self.screen_stack:
            if isinstance(screen, MenuScreen):
                screen.refresh_status()


def main() -> None:
    ZTypeApp().run()


if __name__ == "__main__":
    main()
