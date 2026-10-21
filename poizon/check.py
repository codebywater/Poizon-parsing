"""Self-check: `python -m poizon check` says, step by step and in plain Russian, what works and
what does not — phone, app, current screen, what the parsers see on it.

`diagnose()` only uses the device-adapter interface, so it is tested with a fake device.
"""
import json
from pathlib import Path

from .parse import is_product_page, parse_sizes, parse_specs, parse_title

OK, WARN, FAIL = "ok", "warn", "fail"
ICONS = {OK: "✅", WARN: "⚠️ ", FAIL: "❌"}
DEWU_ANDROID_PACKAGE = "com.shizhuang.duapp"


def diagnose(dev, buy_text="立即购买", package=None):
    """Returns [(status, message)] about the phone and the screen that is open now."""
    out = []

    # Android: is Dewu installed and in front? (iOS adapters launch the app by bundle id.)
    if package and hasattr(dev, "installed"):
        if not dev.installed(package):
            out.append((FAIL, f"Приложение Dewu ({package}) не установлено на телефоне. "
                              "Если у вас другая сборка, передайте её пакет: --package <имя>."))
            return out
        out.append((OK, f"Приложение Dewu установлено ({package})."))
        front = dev.foreground()
        if front != package:
            out.append((FAIL, f"Сейчас на экране другое приложение ({front or 'не определено'}). "
                              "Откройте Dewu на списке товаров или на карточке товара."))
            return out
        out.append((OK, "Dewu открыто на экране."))

    texts = dev.texts()
    if not texts:
        out.append((FAIL, "На экране не найдено ни одного текста. Возможно, экран заблокирован "
                          "или приложение ещё грузится — подождите и запустите проверку снова."))
        return out
    out.append((OK, f"Текстов на экране: {len(texts)}."))

    if is_product_page(texts, buy_text):
        out.append((OK, f"Открыта карточка товара (есть кнопка «{buy_text}»)."))
        title = parse_title(texts)
        out.append((OK, f"Название: {title}") if title else
                   (WARN, "Название не найдено на верхней части экрана: его ищут после первой цены «¥…»."))
        specs = parse_specs(texts)
        if specs.get("article"):
            out.append((OK, f"Артикул (货号) виден сразу: {specs['article']}."))
        else:
            out.append((WARN, "Артикул (货号) не виден на первом экране — это нормально, парсер прокрутит "
                              "карточку вниз до блока 商品信息."))
        prices = [t for t in texts if t.strip().startswith(("¥", "￥"))]
        out.append((OK, f"Цены на экране: {', '.join(prices[:4])}.") if prices else
                   (WARN, "На карточке не найдено ни одной цены «¥…»."))
        return out

    cards = dev.cards()
    if cards:
        out.append((OK, f"Открыт список товаров: карточек с ценой на экране — {len(cards)}."))
        for key, _, _ in cards[:3]:
            out.append((OK, f"  карточка: {key[:70]}"))
        out.append((OK, "Можно запускать: python -m poizon crawl … (обойдёт этот список)."))
        return out

    if parse_sizes(texts):
        out.append((WARN, "Открыто окно выбора размера. Закройте его и вернитесь к карточке или списку."))
        return out

    out.append((FAIL, f"Не похоже ни на список товаров, ни на карточку: нет кнопки «{buy_text}» и нет цен «¥…». "
                      "Откройте в Dewu список товаров (поиск, бренд, категория) или карточку. "
                      "Если экран правильный, а проверка его не узнаёт — сохраните его: "
                      "python -m poizon check … --save out/check и пришлите папку в issue."))
    out.append((WARN, "Первые тексты на экране: " + " | ".join(t[:30] for t in texts[:8])))
    return out


def save_bundle(dev, folder, report):
    """Screenshot, UI tree, texts and the report — everything needed to fix a parser remotely."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    try:
        dev.screenshot(folder / "screen.png")
        saved.append("screen.png")
    except Exception as e:  # a missing screenshot must not hide the rest
        report.append((WARN, f"Скриншот не сохранился: {e}"))
    (folder / "screen.xml").write_text(dev.source(), encoding="utf-8")
    (folder / "texts.json").write_text(json.dumps(dev.texts(), ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "report.txt").write_text(format_report(report), encoding="utf-8")
    return saved + ["screen.xml", "texts.json", "report.txt"]


def format_report(report):
    return "\n".join(f"{ICONS[s]} {m}" for s, m in report)


def worst(report):
    statuses = {s for s, _ in report}
    return FAIL if FAIL in statuses else WARN if WARN in statuses else OK
