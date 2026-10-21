"""Self-check (`python -m poizon check`) against fake phones."""
import json

from poizon.check import FAIL, OK, WARN, diagnose, format_report, save_bundle, worst
from tests.test_crawler import PRODUCT_SPECS, PRODUCT_TOP
from tests.test_parse import SHEET

PKG = "com.shizhuang.duapp"


class Phone:
    def __init__(self, texts=(), cards=(), installed=True, front=PKG):
        self._texts, self._cards = list(texts), list(cards)
        self._installed, self._front = installed, front

    def texts(self):
        return self._texts

    def cards(self):
        return self._cards

    def installed(self, package):
        return self._installed

    def foreground(self):
        return self._front

    def source(self):
        return "<hierarchy/>"

    def screenshot(self, path):
        open(path, "wb").write(b"png")


def messages(report):
    return " ".join(m for _, m in report)


def test_app_not_installed_stops_early():
    report = diagnose(Phone(installed=False), package=PKG)
    assert worst(report) == FAIL and "не установлено" in messages(report)


def test_other_app_in_front():
    report = diagnose(Phone(front="com.android.launcher"), package=PKG)
    assert worst(report) == FAIL and "com.android.launcher" in messages(report)


def test_empty_screen():
    assert worst(diagnose(Phone(texts=[]), package=PKG)) == FAIL


def test_product_page_reports_title_and_prices():
    report = diagnose(Phone(texts=PRODUCT_TOP), package=PKG)
    text = messages(report)
    assert worst(report) == WARN  # article is further down the page — a warning, not an error
    assert "карточка товара" in text and "Timberland" in text and "¥512" in text


def test_product_page_with_article_is_all_ok():
    report = diagnose(Phone(texts=PRODUCT_TOP + PRODUCT_SPECS), package=PKG)
    assert worst(report) == OK and "10061" in messages(report)


def test_list_screen():
    cards = [("Nike Dunk Low|¥899", 600, 780), ("Timberland|¥512", 60, 780)]
    report = diagnose(Phone(texts=["Nike Dunk Low", "¥899"], cards=cards), package=PKG)
    assert worst(report) == OK and "карточек с ценой на экране — 2" in messages(report)


def test_size_sheet_open():
    report = diagnose(Phone(texts=SHEET), package=PKG)
    assert worst(report) == WARN and "выбора размера" in messages(report)


def test_unknown_screen_suggests_saving_it():
    report = diagnose(Phone(texts=["我的", "设置", "消息"]), package=PKG)
    assert worst(report) == FAIL and "--save" in messages(report) and "我的" in messages(report)


def test_ios_without_package_checks_skips_app_step():
    report = diagnose(Phone(texts=PRODUCT_TOP + PRODUCT_SPECS), package=None)
    assert "установлено" not in messages(report) and worst(report) == OK


def test_save_bundle(tmp_path):
    report = [(OK, "x")]
    files = save_bundle(Phone(texts=["¥1"]), tmp_path / "check", report)
    assert files == ["screen.png", "screen.xml", "texts.json", "report.txt"]
    assert json.loads((tmp_path / "check" / "texts.json").read_text(encoding="utf-8")) == ["¥1"]
    assert (tmp_path / "check" / "report.txt").read_text(encoding="utf-8") == format_report(report)
