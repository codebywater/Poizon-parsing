"""Device adapters: the only platform-specific code. Both expose the same small interface
used by poizon.crawler:

    texts() -> [str]            visible texts in document order
    source() -> str             raw UI tree (for dumps)
    cards() -> [(key, x, y)]    product cards on a list screen
    has_text(t) / tap_text(t, timeout) / tap(x, y)
    scroll_down()  back()  close_sheet()  screenshot(path)

Drivers (uiautomator2 / Appium) are imported lazily so the parsers and tests need neither.
"""
import re
import time
import xml.etree.ElementTree as ET

PRICE_RE = re.compile(r"^[¥￥]\s*\d+(?:\.\d+)?\s*起?$")
ANDROID_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
IOS_TEXT_TYPES = ("XCUIElementTypeStaticText", "XCUIElementTypeButton", "XCUIElementTypeOther",
                  "XCUIElementTypeCell")


# --- pure helpers (unit-tested) ----------------------------------------------------------------

def _card_texts(price_node, parent, text_of, max_texts=8):
    """Texts of the smallest ancestor (up to 4 levels) holding >= 2 texts: the product card."""
    card = price_node
    for _ in range(4):
        if card in parent:
            card = parent[card]
        if len([t for t in map(text_of, card.iter()) if t]) >= 2:
            break
    texts = [t for t in map(text_of, card.iter()) if t]
    if len(texts) > max_texts:  # climbed into the whole list: fall back to the price alone
        texts = [text_of(price_node)]
    return texts


def android_texts(xml_source):
    out = []
    for n in ET.fromstring(xml_source).iter("node"):
        t = n.get("text") or n.get("content-desc")
        if t and t.strip():
            out.append(t)
    return out


def android_cards(xml_source):
    """Cards on an Android list screen, found by their ¥price text. Tap point = price centre."""
    root = ET.fromstring(xml_source)
    parent = {c: p for p in root.iter() for c in p}
    text_of = lambda n: (n.get("text") or "").strip()  # noqa: E731
    cards = []
    for n in root.iter("node"):
        if not PRICE_RE.match(text_of(n)):
            continue
        m = ANDROID_BOUNDS.match(n.get("bounds") or "")
        if not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        cards.append(("|".join(_card_texts(n, parent, text_of)), (x1 + x2) // 2, (y1 + y2) // 2))
    return cards


def ios_texts(xml_source):
    """Visible texts in document order. XCUITest exposes them as label/value/name."""
    out = []
    for n in ET.fromstring(xml_source).iter():
        if n.get("visible") == "false" or n.tag not in IOS_TEXT_TYPES:
            continue
        t = n.get("label") or n.get("value") or n.get("name")
        if t and (not out or out[-1] != t):
            out.append(t)
    return out


def ios_cards(xml_source):
    """Cards on an iOS list screen, found by their ¥price text. Tap point = price centre."""
    root = ET.fromstring(xml_source)
    parent = {c: p for p in root.iter() for c in p}

    def text_of(n):
        if n.tag != "XCUIElementTypeStaticText" or n.get("visible") == "false":
            return ""
        return (n.get("label") or n.get("value") or "").strip()

    cards = []
    for n in root.iter("XCUIElementTypeStaticText"):
        if n.get("visible") == "false" or not PRICE_RE.match(text_of(n)):
            continue
        try:
            x = int(n.get("x")) + int(n.get("width")) // 2
            y = int(n.get("y")) + int(n.get("height")) // 2
        except (TypeError, ValueError):
            continue
        cards.append(("|".join(_card_texts(n, parent, text_of)), x, y))
    return cards


# --- Android (uiautomator2) --------------------------------------------------------------------

class AndroidDevice:
    def __init__(self, serial=None):
        import uiautomator2 as u2
        self.d = u2.connect(serial)

    def installed(self, package):
        return package in self.d.app_list(package)

    def foreground(self):
        try:
            return self.d.app_current().get("package")
        except Exception:  # screen off or a system dialog: nothing in focus
            return None

    def source(self):
        return self.d.dump_hierarchy()

    def texts(self):
        return android_texts(self.source())

    def cards(self):
        return android_cards(self.source())

    def has_text(self, t):
        return self.d(textContains=t).exists or self.d(descriptionContains=t).exists

    def tap_text(self, t, timeout=3):
        end = time.time() + timeout
        while True:
            for sel in (self.d(textContains=t), self.d(descriptionContains=t)):
                if sel.exists:
                    sel.click()
                    return True
            if time.time() >= end:
                return False
            time.sleep(0.5)

    def tap(self, x, y):
        self.d.click(x, y)

    def scroll_down(self):
        self.d.swipe_ext("up", scale=0.6)

    def back(self):
        self.d.press("back")

    close_sheet = back

    def screenshot(self, path):
        self.d.screenshot(str(path))


# --- iOS (Appium + XCUITest) -------------------------------------------------------------------

class IOSDevice:
    def __init__(self, udid, bundle_id="com.siwuai.duapp", server="http://127.0.0.1:4723",
                 team_id=None, wda_bundle_id=None):
        from appium import webdriver
        from appium.options.ios import XCUITestOptions
        opts = XCUITestOptions()
        opts.udid = udid
        opts.bundle_id = bundle_id
        opts.no_reset = True  # keep login and the screen that is open
        if team_id:  # let Appium sign WebDriverAgent itself
            opts.xcode_org_id = team_id
            opts.xcode_signing_id = "Apple Development"
        if wda_bundle_id:
            opts.updated_wda_bundle_id = wda_bundle_id
        self.d = webdriver.Remote(server, options=opts)
        size = self.d.get_window_size()
        self.w, self.h = size["width"], size["height"]

    def quit(self):
        self.d.quit()

    def source(self):
        return self.d.page_source

    def texts(self):
        return ios_texts(self.source())

    def cards(self):
        return ios_cards(self.source())

    def _find(self, t):
        from appium.webdriver.common.appiumby import AppiumBy
        q = t.replace("\\", "\\\\").replace('"', '\\"')
        return self.d.find_elements(AppiumBy.IOS_PREDICATE, f'label CONTAINS "{q}" OR name CONTAINS "{q}"')

    def has_text(self, t):
        return bool(self._find(t))

    def tap_text(self, t, timeout=3):
        end = time.time() + timeout
        while True:
            els = self._find(t)
            if els:
                els[0].click()
                return True
            if time.time() >= end:
                return False
            time.sleep(0.5)

    def tap(self, x, y):
        self.d.execute_script("mobile: tap", {"x": int(x), "y": int(y)})

    def _drag(self, fx, fy, tx, ty, duration=0.4):
        self.d.execute_script("mobile: dragFromToForDuration", {
            "fromX": int(fx), "fromY": int(fy), "toX": int(tx), "toY": int(ty), "duration": duration})

    def scroll_down(self):
        self._drag(self.w / 2, self.h * 0.75, self.w / 2, self.h * 0.35)

    def back(self):  # iOS edge-swipe back gesture
        self._drag(3, self.h / 2, self.w * 0.8, self.h / 2, 0.3)

    def close_sheet(self):  # tapping the dimmed area above a bottom sheet dismisses it
        self.tap(self.w * 0.5, self.h * 0.08)

    def screenshot(self, path):
        self.d.save_screenshot(str(path))
