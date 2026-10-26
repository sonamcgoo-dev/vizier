"""
Vizier brand layer â€” the midnight-palace look.

The visual language is deliberately *adjacent* to the familiar desert-palace
fantasy: midnight indigo, antique gold, deep crimson, and a thread of
turquoise.  Nothing here copies a film asset; the wordmark uses the open
source Rakkas display face and the ornament is ordinary geometric
calligraphy.

Everything animated is routed through :func:`animations_enabled` so headless
tests, smoke builds, and users who prefer reduced motion still get a stable,
instant interface.
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplashScreen,
    QVBoxLayout,
    QWidget,
)

from vizier.utils import get_asset_path

# ---------------------------------------------------------------------------
# Palette â€” single source of truth for the GUI
# ---------------------------------------------------------------------------

INK = "#0B0A17"
INK_DEEP = "#07060E"
INK_SOFT = "#12101F"
SURFACE = "#17142A"
SURFACE_RAISED = "#201B38"

GOLD = "#D4A857"
GOLD_BRIGHT = "#F2D79A"
GOLD_PALE = "#F8EBC8"
GOLD_DEEP = "#8C6A2A"

CRIMSON = "#8E1B2C"
CRIMSON_BRIGHT = "#C8324A"
CRIMSON_DEEP = "#5C0F1D"

TURQUOISE = "#4FD1C5"
TURQUOISE_DEEP = "#1F6F6A"

IVORY = "#F5EFE2"
IVORY_DIM = "#B9B2C7"
IVORY_MUTED = "#817A92"

TAGLINE = "THE ROYAL ADVISOR  Â·  LOCAL INTELLIGENCE, ABSOLUTE PRIVACY"
TAGLINE_COMPACT = "THE ROYAL ADVISOR"


# ---------------------------------------------------------------------------
# Display font
# ---------------------------------------------------------------------------

_DISPLAY_CANDIDATES = (
    "Rakkas",
    "Cinzel Decorative",
    "Palatino Linotype",
    "Georgia",
)
_display_family = "Georgia"
_display_loaded = False


def load_display_font() -> str:
    """Register the bundled display face and return the family to use."""
    global _display_family, _display_loaded
    if _display_loaded:
        return _display_family
    _display_loaded = True
    if QApplication.instance() is None:
        return _display_family
    font_path = get_asset_path("fonts", "Rakkas-Regular.ttf")
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _display_family = families[0]
                return _display_family
    available = set(QFontDatabase.families())
    for candidate in _DISPLAY_CANDIDATES:
        if candidate in available:
            _display_family = candidate
            break
    return _display_family


def display_family() -> str:
    """Return the active display font family (loading it once if needed)."""
    return load_display_font()


def display_font(pixel_size: int, *, spacing: float | None = None) -> QFont:
    """Build a display font with a little air between the letters."""
    font = QFont(display_family())
    font.setPixelSize(max(8, int(pixel_size)))
    font.setWeight(QFont.Weight.Normal)
    if spacing is None:
        spacing = max(1.0, pixel_size * 0.05)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------

def animations_enabled() -> bool:
    """True only when motion is safe and welcome."""
    for flag in ("VIZIER_REDUCED_MOTION", "VIZIER_SMOKE_TEST"):
        value = os.environ.get(flag, "").strip().lower()
        if value not in ("", "0", "false", "no", "off"):
            return False
    platform = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
    if platform in ("offscreen", "minimal", "vnc"):
        return False
    return QApplication.instance() is not None


def fade_in_window(widget: QWidget, duration: int = 320) -> QPropertyAnimation | None:
    """Fade a top-level window in.  Harmless when motion is disabled."""
    if not animations_enabled():
        widget.setWindowOpacity(1.0)
        return None
    widget.setWindowOpacity(0.0)
    animation = QPropertyAnimation(widget, b"windowOpacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def fade_in_widget(widget: QWidget, duration: int = 260) -> QPropertyAnimation | None:
    """Fade a child widget in using an opacity effect."""
    if not animations_enabled():
        return None
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        # Leaving an opacity effect attached forces an offscreen paint pass
        # for the whole widget tree; drop it once the fade is done.
        widget.setGraphicsEffect(None)

    animation.finished.connect(_cleanup)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


# ---------------------------------------------------------------------------
# Painting helpers
# ---------------------------------------------------------------------------

def _star_path(cx: float, cy: float, radius: float) -> QPainterPath:
    """A slim four-point star â€” the recurring ornament of the theme."""
    inner = radius * 0.16
    path = QPainterPath(QPointF(cx, cy - radius))
    path.quadTo(cx + inner, cy - inner, cx + radius, cy)
    path.quadTo(cx + inner, cy + inner, cx, cy + radius)
    path.quadTo(cx - inner, cy + inner, cx - radius, cy)
    path.quadTo(cx - inner, cy - inner, cx, cy - radius)
    path.closeSubpath()
    return path


def _arch_path(x: float, y: float, width: float, height: float) -> QPainterPath:
    """A pointed Moorish arch, drawn as an open outline."""
    path = QPainterPath(QPointF(x, y + height))
    path.lineTo(x, y + height * 0.48)
    path.cubicTo(
        x, y + height * 0.18,
        x + width * 0.30, y + height * 0.02,
        x + width / 2, y,
    )
    path.cubicTo(
        x + width * 0.70, y + height * 0.02,
        x + width, y + height * 0.18,
        x + width, y + height * 0.48,
    )
    path.lineTo(x + width, y + height)
    return path


def paint_wordmark(
    painter: QPainter,
    text: str,
    x: float,
    baseline: float,
    pixel_size: int,
) -> float:
    """Paint the gilded wordmark.  Returns the advance width."""
    font = display_font(pixel_size)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(font)
    path = QPainterPath()
    path.addText(float(x), float(baseline), font, text)
    bounds = path.boundingRect()

    gradient = QLinearGradient(0.0, bounds.top(), 0.0, bounds.bottom())
    gradient.setColorAt(0.00, QColor(GOLD_PALE))
    gradient.setColorAt(0.32, QColor(GOLD_BRIGHT))
    gradient.setColorAt(0.58, QColor(GOLD))
    gradient.setColorAt(0.82, QColor("#B78A3F"))
    gradient.setColorAt(1.00, QColor(GOLD_DEEP))

    glow = QColor(GOLD_BRIGHT)
    glow.setAlpha(22)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)):
        painter.save()
        painter.translate(dx, dy)
        painter.drawPath(path)
        painter.restore()

    outline = QPen(QColor(58, 38, 10, 150))
    outline.setWidthF(max(0.6, pixel_size / 70.0))
    painter.setPen(outline)
    painter.setBrush(gradient)
    painter.drawPath(path)
    painter.restore()
    return QFontMetricsF(font).horizontalAdvance(text)


def paint_wordmark_centered(
    painter: QPainter,
    text: str,
    center_x: float,
    baseline: float,
    pixel_size: int,
) -> None:
    width = QFontMetricsF(display_font(pixel_size)).horizontalAdvance(text)
    paint_wordmark(painter, text, center_x - width / 2.0, baseline, pixel_size)


def _paint_arches(
    painter: QPainter,
    rect: QRectF,
    *,
    alpha: int = 18,
    width: float = 220.0,
    height: float = 330.0,
) -> None:
    pen = QPen(QColor(212, 168, 87, alpha))
    pen.setWidthF(1.1)
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(pen)
    x = rect.left() - width * 0.35
    top = rect.top() + rect.height() * 0.16
    while x < rect.right():
        painter.drawPath(_arch_path(x, top, width, height))
        painter.drawPath(_arch_path(x + 12, top + 20, width - 24, height - 24))
        x += width + 38
    painter.restore()


def _paint_stars(painter: QPainter, rect: QRectF, alpha: int = 20) -> None:
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    colour = QColor(GOLD_BRIGHT)
    colour.setAlpha(alpha)
    painter.setBrush(colour)
    for index in range(26):
        x = rect.left() + (index * 149.7 + 41) % max(1.0, rect.width())
        y = rect.top() + (index * 97.3 + 23) % max(1.0, rect.height())
        radius = 1.2 + (index % 3) * 0.7
        painter.drawPath(_star_path(x, y, radius))
    painter.restore()


# ---------------------------------------------------------------------------
# Wordmark widget
# ---------------------------------------------------------------------------

class Wordmark(QWidget):
    """The gilded VIZIER wordmark, painted rather than styled."""

    def __init__(
        self,
        text: str = "VIZIER",
        pixel_size: int = 46,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._text = text
        self._pixel_size = pixel_size
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.setFixedHeight(int(pixel_size * 1.16) + 4)

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QSize:
        metrics = QFontMetricsF(display_font(self._pixel_size))
        width = metrics.horizontalAdvance(self._text)
        return QSize(int(width) + 12, self.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        metrics = QFontMetricsF(display_font(self._pixel_size))
        baseline = (self.height() + metrics.ascent() - metrics.descent()) / 2.0
        paint_wordmark(painter, self._text, 2.0, baseline, self._pixel_size)


# ---------------------------------------------------------------------------
# Backdrop and ornaments
# ---------------------------------------------------------------------------

class PalaceBackdrop(QWidget):
    """The painted midnight hall behind the whole application."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        base = QLinearGradient(0.0, rect.top(), 0.0, rect.bottom())
        base.setColorAt(0.00, QColor("#0D0B1E"))
        base.setColorAt(0.45, QColor(INK))
        base.setColorAt(1.00, QColor(INK_DEEP))
        painter.fillRect(rect, QBrush(base))

        gold_glow = QRadialGradient(
            QPointF(rect.width() * 0.78, -rect.height() * 0.05),
            max(rect.width(), rect.height()) * 0.62,
        )
        gold_glow.setColorAt(0.0, QColor(212, 168, 87, 38))
        gold_glow.setColorAt(0.55, QColor(142, 27, 44, 16))
        gold_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, QBrush(gold_glow))

        teal_glow = QRadialGradient(
            QPointF(rect.width() * 0.08, rect.height() * 0.92),
            max(rect.width(), rect.height()) * 0.48,
        )
        teal_glow.setColorAt(0.0, QColor(79, 209, 197, 26))
        teal_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, QBrush(teal_glow))

        _paint_arches(painter, rect, alpha=16, width=230, height=360)
        _paint_stars(painter, rect, alpha=22)

        pen = QPen(QColor(212, 168, 87, 70))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawLine(rect.topLeft(), rect.topRight())


class OrnamentDivider(QWidget):
    """A hairline with a four-point star at its centre."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(16)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        centre_y = self.height() / 2.0
        centre_x = self.width() / 2.0
        line = QLinearGradient(0.0, centre_y, self.width(), centre_y)
        line.setColorAt(0.0, QColor(212, 168, 87, 0))
        line.setColorAt(0.25, QColor(212, 168, 87, 90))
        line.setColorAt(0.5, QColor(242, 215, 154, 170))
        line.setColorAt(0.75, QColor(212, 168, 87, 90))
        line.setColorAt(1.0, QColor(212, 168, 87, 0))
        pen = QPen(QBrush(line), 1.0)
        painter.setPen(pen)
        painter.drawLine(0, int(centre_y), self.width(), int(centre_y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(GOLD_BRIGHT))
        painter.drawPath(_star_path(centre_x, centre_y, 5.0))

        small = QColor(GOLD)
        small.setAlpha(160)
        painter.setBrush(small)
        painter.drawPath(_star_path(centre_x - 42, centre_y, 2.2))
        painter.drawPath(_star_path(centre_x + 42, centre_y, 2.2))


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

class BrandHeader(QWidget):
    """Gilded band with the wordmark; used by the window and every dialog."""

    def __init__(
        self,
        title: str = "",
        *,
        compact: bool = False,
        card: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._compact = compact
        self._card = card
        self._title = title
        self._shimmer_phase = -1.0
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(40)
        self._shimmer_timer.timeout.connect(self._tick_shimmer)
        self._shimmer_delay = QTimer(self)
        self._shimmer_delay.setSingleShot(True)
        self._shimmer_delay.setInterval(2600)
        self._shimmer_delay.timeout.connect(self._start_shimmer)

        size = 34 if compact else 52
        self.setMinimumHeight(74 if compact else 104)

        outer = QHBoxLayout(self)
        if card:
            outer.setContentsMargins(20, 9, 20, 9)
        else:
            outer.setContentsMargins(24, 10, 24, 9)
        outer.setSpacing(18)

        brand_column = QVBoxLayout()
        brand_column.setSpacing(0)
        brand_column.setContentsMargins(0, 0, 0, 0)
        self.wordmark = Wordmark("VIZIER", size, self)
        brand_column.addWidget(self.wordmark)

        tagline = QLabel(TAGLINE_COMPACT if compact else TAGLINE, self)
        tagline.setStyleSheet(
            f"color:{GOLD}; font-family:'Segoe UI'; font-size:"
            f"{'7' if compact else '8'}pt; letter-spacing:2px;"
            " background:transparent;"
        )
        tagline.setContentsMargins(2, 0, 0, 0)
        brand_column.addWidget(tagline)
        outer.addLayout(brand_column)

        self._corner = QHBoxLayout()
        self._corner.setSpacing(12)

        if title:
            rule = QFrame(self)
            rule.setFixedWidth(1)
            rule.setFixedHeight(34 if compact else 46)
            rule.setStyleSheet(
                "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 rgba(212,168,87,0), stop:0.5 rgba(212,168,87,150),"
                " stop:1 rgba(212,168,87,0)); border:none;"
            )
            outer.addSpacing(2)
            outer.addWidget(rule)
            section = QLabel(title.upper(), self)
            section.setStyleSheet(
                f"color:{GOLD_BRIGHT}; font-family:'Segoe UI'; font-size:"
                f"{'11' if compact else '13'}pt; font-weight:600;"
                " letter-spacing:4px; background:transparent;"
            )
            outer.addWidget(section)
            outer.addSpacing(4)

        outer.addStretch(1)
        outer.addLayout(self._corner)

    def add_corner_widget(self, widget: QWidget) -> None:
        """Place a widget at the right edge of the header."""
        self._corner.addWidget(
            widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if animations_enabled():
            self._shimmer_delay.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._shimmer_delay.stop()
        self._shimmer_timer.stop()

    def _start_shimmer(self) -> None:
        if not self.isVisible() or not animations_enabled():
            return
        self._shimmer_phase = 0.0
        self._shimmer_timer.start()

    def _tick_shimmer(self) -> None:
        self._shimmer_phase += 0.022
        if self._shimmer_phase >= 1.0:
            self._shimmer_timer.stop()
            self._shimmer_phase = -1.0
            self._shimmer_delay.start()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 16.0 if self._card else 0.0

        panel = QPainterPath()
        if radius:
            panel.addRoundedRect(rect, radius, radius)
        else:
            panel.addRect(rect)

        fill = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        fill.setColorAt(0.00, QColor(31, 26, 56, 238))
        fill.setColorAt(0.42, QColor(20, 17, 38, 232))
        fill.setColorAt(1.00, QColor(11, 9, 24, 228))
        painter.fillPath(panel, fill)

        # Faint court geometry behind the type.
        painter.save()
        painter.setClipPath(panel)
        _paint_arches(
            painter,
            QRectF(rect.right() - rect.width() * 0.55, rect.top() - 40,
                   rect.width() * 0.55, rect.height() + 80),
            alpha=16,
            width=150,
            height=210,
        )
        _paint_stars(painter, rect, alpha=16)

        if 0.0 <= self._shimmer_phase <= 1.0:
            centre = rect.left() - rect.width() * 0.35
            centre += self._shimmer_phase * rect.width() * 1.7
            band = QLinearGradient(centre - 160, 0.0, centre + 160, 0.0)
            band.setColorAt(0.0, QColor(255, 240, 200, 0))
            band.setColorAt(0.5, QColor(255, 240, 200, 26))
            band.setColorAt(1.0, QColor(255, 240, 200, 0))
            painter.fillRect(rect, QBrush(band))
        painter.restore()

        edge = QPen(QColor(212, 168, 87, 120 if self._card else 75))
        edge.setWidthF(1.0)
        painter.setPen(edge)
        if radius:
            painter.drawPath(panel)
        else:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if self._card:
            inner = rect.adjusted(4, 4, -4, -4)
            inner_path = QPainterPath()
            inner_path.addRoundedRect(inner, radius - 4, radius - 4)
            painter.setPen(QPen(QColor(212, 168, 87, 34), 1.0))
            painter.drawPath(inner_path)


# ---------------------------------------------------------------------------
# Status pill
# ---------------------------------------------------------------------------

class StateOrb(QWidget):
    """Small jewelled indicator that breathes while the agent is working."""

    _COLOURS = {
        "IDLE": GOLD,
        "READY": TURQUOISE,
        "THINKING": TURQUOISE,
        "TOOLS": GOLD_BRIGHT,
        "WORKING": TURQUOISE,
        "LOADING": GOLD_BRIGHT,
        "ERROR": CRIMSON_BRIGHT,
    }
    _ACTIVE = {"THINKING", "TOOLS", "WORKING", "LOADING", "BUSY"}

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._state = "IDLE"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)

    def state(self) -> str:
        return self._state

    def set_state(self, state: str) -> None:
        self._state = state.upper()
        if self._state in self._ACTIVE and animations_enabled() and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._state in self._ACTIVE and animations_enabled():
            self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _tick(self) -> None:
        self._phase += 0.18
        if self._phase > math.tau:
            self._phase -= math.tau
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        centre = QPointF(self.width() / 2.0, self.height() / 2.0)
        colour = QColor(self._COLOURS.get(self._state, GOLD))
        active = self._state in self._ACTIVE
        pulse = 0.5 + 0.5 * math.sin(self._phase) if active else 0.0

        if active:
            halo = QRadialGradient(centre, 11.0)
            halo_colour = QColor(colour)
            halo_colour.setAlpha(int(30 + 60 * pulse))
            halo.setColorAt(0.0, halo_colour)
            halo.setColorAt(1.0, QColor(colour.red(), colour.green(), colour.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(centre, 10.5, 10.5)

        ring = QColor(colour)
        ring.setAlpha(120)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(ring, 1.0))
        painter.drawEllipse(centre, 7.0, 7.0)

        core = QColor(colour)
        core.setAlpha(255)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(centre, 3.6 + 0.5 * pulse, 3.6 + 0.5 * pulse)

        spark = QColor(GOLD_PALE)
        spark.setAlpha(190)
        painter.setBrush(spark)
        painter.drawPath(_star_path(centre.x(), centre.y(), 1.4))


class StatusPill(QWidget):
    """Orb + state caption, sized for the top-right corner."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.orb = StateOrb(self)
        self.label = QLabel("IDLE", self)
        self.label.setObjectName("StateLabel")
        layout.addWidget(self.orb)
        layout.addWidget(self.label)
        self.set_state("IDLE")

    def set_state(self, state: str) -> None:
        text = state.upper()
        self.orb.set_state(text)
        self.label.setText(text)
        colour = StateOrb._COLOURS.get(text, GOLD)
        self.label.setStyleSheet(
            f"color:{colour}; font-family:'Segoe UI'; font-size:9pt;"
            " font-weight:600; letter-spacing:2px; background:transparent;"
        )


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class BrandedDialog(QDialog):
    """Base dialog that carries the wordmark and fades in on first show."""

    brand_title = ""
    brand_card = True

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.brand_header: BrandHeader | None = None
        self._branded_fade_started = False

    def finalize_brand(self, title: str | None = None) -> None:
        if self.brand_header is not None:
            return
        layout = self.layout()
        if layout is None:
            return
        header = BrandHeader(
            title if title is not None else self.brand_title,
            compact=True,
            card=self.brand_card,
            parent=self,
        )
        layout.insertWidget(0, header)
        self.brand_header = header
        if layout.contentsMargins().left() < 12:
            layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(max(layout.spacing(), 10))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._branded_fade_started:
            self._branded_fade_started = True
            fade_in_window(self, 220)


# ---------------------------------------------------------------------------
# Splash + reveal
# ---------------------------------------------------------------------------

def _paint_court_panel(
    painter: QPainter,
    rect: QRectF,
) -> None:
    base = QLinearGradient(0.0, rect.top(), 0.0, rect.bottom())
    base.setColorAt(0.00, QColor("#100D24"))
    base.setColorAt(0.55, QColor("#0B0918"))
    base.setColorAt(1.00, QColor(INK_DEEP))
    painter.fillRect(rect, QBrush(base))

    glow = QRadialGradient(
        QPointF(rect.width() * 0.70, rect.height() * 0.22),
        rect.width() * 0.58,
    )
    glow.setColorAt(0.0, QColor(212, 168, 87, 52))
    glow.setColorAt(0.45, QColor(142, 27, 44, 20))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.fillRect(rect, QBrush(glow))

    teal = QRadialGradient(
        QPointF(rect.width() * 0.12, rect.height() * 0.85),
        rect.width() * 0.42,
    )
    teal.setColorAt(0.0, QColor(79, 209, 197, 34))
    teal.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.fillRect(rect, QBrush(teal))

    _paint_arches(painter, rect, alpha=22, width=190, height=300)
    _paint_stars(painter, rect, alpha=26)

    frame = rect.adjusted(14, 14, -14, -14)
    path = QPainterPath()
    path.addRoundedRect(frame, 18, 18)
    painter.setPen(QPen(QColor(212, 168, 87, 150), 1.2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    inner = frame.adjusted(5, 5, -5, -5)
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner, 14, 14)
    painter.setPen(QPen(QColor(212, 168, 87, 44), 1.0))
    painter.drawPath(inner_path)


def create_splash(version: str = "") -> QSplashScreen | None:
    """Build the cinematic splash.  Returns None when motion is off."""
    if not animations_enabled():
        return None
    app = QApplication.instance()
    screen = app.primaryScreen() if app else None
    ratio = float(screen.devicePixelRatio()) if screen else 1.0
    width, height = 780, 430

    pixmap = QPixmap(int(width * ratio), int(height * ratio))
    pixmap.fill(QColor(INK_DEEP))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(ratio, ratio)
    rect = QRectF(0, 0, width, height)
    _paint_court_panel(painter, rect)

    paint_wordmark_centered(painter, "VIZIER", width / 2.0, 196, 118)

    tagline = QFont("Segoe UI")
    tagline.setPixelSize(12)
    tagline.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5.0)
    painter.setFont(tagline)
    painter.setPen(QColor(GOLD_BRIGHT))
    painter.drawText(
        QRectF(0, 224, width, 30),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        "THE ROYAL ADVISOR",
    )

    centre = width / 2.0
    line = QLinearGradient(centre - 190, 0.0, centre + 190, 0.0)
    line.setColorAt(0.0, QColor(212, 168, 87, 0))
    line.setColorAt(0.5, QColor(242, 215, 154, 180))
    line.setColorAt(1.0, QColor(212, 168, 87, 0))
    painter.setPen(QPen(QBrush(line), 1.0))
    painter.drawLine(int(centre - 190), 278, int(centre + 190), 278)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(GOLD_BRIGHT))
    painter.drawPath(_star_path(centre, 278, 5.0))

    message = QFont("Segoe UI")
    message.setPixelSize(10)
    message.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.0)
    painter.setFont(message)
    painter.setPen(QColor(IVORY_DIM))
    painter.drawText(
        QRectF(0, 320, width, 24),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        "SUMMONING THE COURT",
    )

    if version:
        tiny = QFont("Segoe UI")
        tiny.setPixelSize(9)
        painter.setFont(tiny)
        painter.setPen(QColor(IVORY_MUTED))
        painter.drawText(
            QRectF(0, height - 42, width - 26, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"v{version}",
        )
    painter.end()
    pixmap.setDevicePixelRatio(ratio)

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return splash


def reveal_window(window: QWidget, splash: QSplashScreen | None = None) -> None:
    """Show the main window and dissolve the splash."""
    window.show()
    fade_in_window(window, 380)
    if splash is None:
        return
    animation = QPropertyAnimation(splash, b"windowOpacity", splash)
    animation.setDuration(260)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.Type.InCubic)
    animation.finished.connect(splash.close)
    animation.finished.connect(splash.deleteLater)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

