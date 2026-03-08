"""
TimelineJS3 builder — zero external dependencies.

Builds TimelineJS3 JSON data structures and generates standalone HTML
files that render interactive historical timelines in any browser.
"""

import json
from typing import Any, Optional


# CDN URLs for TimelineJS3
_CSS_CDN = "https://cdn.knightlab.com/libs/timeline3/latest/css/timeline.css"
_JS_CDN = "https://cdn.knightlab.com/libs/timeline3/latest/js/timeline.js"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="{css_cdn}">
  <script src="{js_cdn}"></script>
  <style>
    html, body {{ height: 100%; margin: 0; padding: 0; background: {bg_color}; }}
    #timeline-embed {{ width: 100%; height: 100%; }}
  </style>
</head>
<body>
  <div id="timeline-embed"></div>
  <script>
    var timelineData = {json_data};
    var options = {options};
    new TL.Timeline('timeline-embed', timelineData, options);
  </script>
</body>
</html>
"""


def _make_date(
    year: int,
    month: Optional[int] = None,
    day: Optional[int] = None,
    display_date: Optional[str] = None,
) -> dict[str, Any]:
    """Build a TimelineJS3 date object."""
    d: dict[str, Any] = {"year": year}
    if month is not None:
        d["month"] = month
    if day is not None:
        d["day"] = day
    if display_date is not None:
        d["display_date"] = display_date
    return d


class TimelineBuilder:
    """Fluent builder for TimelineJS3 timeline data.

    Parameters
    ----------
    title : str
        Timeline title (displayed on the intro slide).
    subtitle : str, optional
        Body text for the intro slide (HTML supported).
    title_media_url : str, optional
        Media URL for the title slide.
    title_media_caption : str, optional
        Caption for the title slide media.
    scale : str
        ``"human"`` (default) or ``"cosmological"``.
    """

    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        title_media_url: Optional[str] = None,
        title_media_caption: Optional[str] = None,
        scale: str = "human",
    ) -> None:
        self._title: dict[str, Any] = {
            "text": {"headline": title},
        }
        if subtitle:
            self._title["text"]["text"] = subtitle
        if title_media_url:
            media: dict[str, str] = {"url": title_media_url}
            if title_media_caption:
                media["caption"] = title_media_caption
            self._title["media"] = media

        self._events: list[dict[str, Any]] = []
        self._eras: list[dict[str, Any]] = []
        self._scale = scale

    def add_event(
        self,
        start_year: int,
        headline: str,
        *,
        start_month: Optional[int] = None,
        start_day: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
        end_day: Optional[int] = None,
        body: Optional[str] = None,
        group: Optional[str] = None,
        display_date: Optional[str] = None,
        media_url: Optional[str] = None,
        media_caption: Optional[str] = None,
        media_credit: Optional[str] = None,
        background_color: Optional[str] = None,
        unique_id: Optional[str] = None,
    ) -> "TimelineBuilder":
        """Add an event to the timeline.

        Parameters
        ----------
        start_year : int
            Event year. Use negative for BCE (e.g., ``-551``).
        headline : str
            Event title.
        body : str, optional
            Event description (HTML supported).
        group : str, optional
            Group label for row clustering.
        display_date : str, optional
            Custom date display text.
        media_url : str, optional
            URL of image, video, or other media.
        """
        event: dict[str, Any] = {
            "start_date": _make_date(start_year, start_month, start_day),
            "text": {"headline": headline},
        }
        if body:
            event["text"]["text"] = body
        if end_year is not None:
            event["end_date"] = _make_date(end_year, end_month, end_day)
        if group:
            event["group"] = group
        if display_date:
            event["display_date"] = display_date
        if media_url:
            media: dict[str, str] = {"url": media_url}
            if media_caption:
                media["caption"] = media_caption
            if media_credit:
                media["credit"] = media_credit
            event["media"] = media
        if background_color:
            event["background"] = {"color": background_color}
        if unique_id:
            event["unique_id"] = unique_id

        self._events.append(event)
        return self

    def add_era(
        self,
        start_year: int,
        end_year: int,
        headline: str,
        *,
        start_month: Optional[int] = None,
        start_day: Optional[int] = None,
        end_month: Optional[int] = None,
        end_day: Optional[int] = None,
        color: Optional[str] = None,
    ) -> "TimelineBuilder":
        """Add a labeled era (background band) to the timeline.

        Parameters
        ----------
        start_year : int
            Era start year. Negative for BCE.
        end_year : int
            Era end year.
        headline : str
            Era label displayed on the timeline.
        color : str, optional
            Background color (hex or CSS name). Note: era colors are
            auto-assigned by TimelineJS3; this sets the text headline only.
        """
        era: dict[str, Any] = {
            "start_date": _make_date(start_year, start_month, start_day),
            "end_date": _make_date(end_year, end_month, end_day),
            "text": {"headline": headline},
        }
        self._eras.append(era)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return the timeline as a Python dict (TimelineJS3 JSON format)."""
        data: dict[str, Any] = {
            "title": self._title,
            "events": self._events,
            "scale": self._scale,
        }
        if self._eras:
            data["eras"] = self._eras
        return data

    def to_json(self, **kwargs: Any) -> str:
        """Return the timeline as a JSON string."""
        kwargs.setdefault("ensure_ascii", False)
        kwargs.setdefault("indent", 2)
        return json.dumps(self.to_dict(), **kwargs)

    def save_html(
        self,
        path: str,
        *,
        font: Optional[str] = None,
        language: str = "en",
        initial_zoom: Optional[int] = None,
        timenav_position: str = "bottom",
        hash_bookmark: bool = False,
        start_at_end: bool = False,
        start_at_slide: int = 0,
        default_bg_color: str = "white",
        duration: int = 1000,
        use_bc: bool = False,
    ) -> str:
        """Write a standalone HTML file with the embedded timeline.

        Parameters
        ----------
        path : str
            Output file path.
        font : str, optional
            Built-in font pair (e.g., ``"Georgia-Helvetica"``) or CSS URL.
        language : str
            Interface language code (e.g., ``"en"``, ``"zh-cn"``, ``"ja"``).
        initial_zoom : int, optional
            Starting zoom level index.
        timenav_position : str
            ``"top"`` or ``"bottom"`` (default).
        hash_bookmark : bool
            Update URL hash on slide navigation.
        start_at_end : bool
            Start at the last event.
        start_at_slide : int
            Index of initial slide (0 = title).
        default_bg_color : str
            Background color (hex or CSS name).
        duration : int
            Animation duration in milliseconds.
        use_bc : bool
            Use "BC" instead of "BCE" for negative years.

        Returns
        -------
        str
            The absolute path of the written file.
        """
        options: dict[str, Any] = {
            "language": language,
            "timenav_position": timenav_position,
            "hash_bookmark": hash_bookmark,
            "start_at_end": start_at_end,
            "start_at_slide": start_at_slide,
            "default_bg_color": default_bg_color,
            "duration": duration,
            "use_bc": use_bc,
        }
        if font is not None:
            options["font"] = font
        if initial_zoom is not None:
            options["initial_zoom"] = initial_zoom

        title_text = self._title.get("text", {}).get("headline", "Timeline")

        html = _HTML_TEMPLATE.format(
            lang=language[:2],
            title=title_text,
            css_cdn=_CSS_CDN,
            js_cdn=_JS_CDN,
            bg_color=default_bg_color,
            json_data=self.to_json(),
            options=json.dumps(options, ensure_ascii=False),
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        return path


# ------------------------------------------------------------------
# Demo
# ------------------------------------------------------------------

def main() -> None:
    tl = TimelineBuilder(
        title="Major Chinese Dynasties",
        subtitle="<p>A timeline of key events in Chinese history</p>",
    )

    # Eras
    tl.add_era(-221, -206, "Qin")
    tl.add_era(-206, 220, "Han")
    tl.add_era(618, 907, "Tang")
    tl.add_era(960, 1279, "Song")
    tl.add_era(1368, 1644, "Ming")
    tl.add_era(1644, 1912, "Qing")

    # Events
    tl.add_event(
        start_year=-551,
        end_year=-479,
        headline="Confucius (孔子)",
        body="<p>Philosopher whose teachings shaped Chinese civilization for millennia.</p>",
        group="Philosophy",
        display_date="551–479 BCE",
    )
    tl.add_event(
        start_year=-221,
        headline="Qin Shi Huang unifies China",
        body="<p>First emperor of a unified China. Standardized weights, measures, and writing.</p>",
        group="Politics",
    )
    tl.add_event(
        start_year=-104,
        headline="Sima Qian completes Shiji (史記)",
        body="<p>The first comprehensive history of China, covering 3,000 years.</p>",
        group="Culture",
    )
    tl.add_event(
        start_year=105,
        headline="Cai Lun improves papermaking",
        body="<p>Refined the process of making paper from bark, hemp, and rags.</p>",
        group="Technology",
    )
    tl.add_event(
        start_year=618, start_month=6, start_day=18,
        headline="Li Yuan founds the Tang Dynasty",
        body="<p>Beginning of one of China's most cosmopolitan and culturally rich eras.</p>",
        group="Politics",
    )
    tl.add_event(
        start_year=701,
        end_year=762,
        headline="Li Bai (李白)",
        body="<p>One of the greatest Chinese poets, known as the 'Immortal Poet'.</p>",
        group="Culture",
    )
    tl.add_event(
        start_year=1405,
        end_year=1433,
        headline="Zheng He's voyages",
        body="<p>Seven maritime expeditions reaching Southeast Asia, India, Arabia, and East Africa.</p>",
        group="Exploration",
    )
    tl.add_event(
        start_year=1644,
        headline="Fall of the Ming Dynasty",
        body="<p>Li Zicheng captures Beijing; the Manchu Qing dynasty takes power.</p>",
        group="Politics",
    )

    output = tl.save_html("chinese_dynasties_demo.html", language="en")
    print(f"Timeline saved to: {output}")
    print(f"\nJSON preview:\n{tl.to_json()[:500]}...")


if __name__ == "__main__":
    main()
