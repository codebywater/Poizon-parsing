from poizon.devices import android_cards, android_texts, ios_cards, ios_texts

ANDROID = """<hierarchy><node text="" bounds="[0,0][1080,2400]">
<node text="" bounds="[0,500][540,900]">
<node text="Timberland Martin boot" bounds="[10,700][500,740]"/>
<node text="¥512" bounds="[10,760][110,800]"/></node>
<node text="" bounds="[540,500][1080,900]">
<node text="Nike Dunk Low" bounds="[550,700][1000,740]"/>
<node text="¥899" bounds="[550,760][650,800]"/></node>
<node text="" content-desc="立即购买" bounds="[0,0][1,1]"/></node></hierarchy>"""

IOS = """<AppiumAUT><XCUIElementTypeApplication><XCUIElementTypeCollectionView>
<XCUIElementTypeCell>
<XCUIElementTypeStaticText label="Timberland Martin boot" x="10" y="300" width="150" height="20" visible="true"/>
<XCUIElementTypeStaticText label="¥512" x="10" y="330" width="60" height="20" visible="true"/>
</XCUIElementTypeCell>
<XCUIElementTypeCell>
<XCUIElementTypeStaticText label="Nike Dunk Low" x="200" y="300" width="150" height="20" visible="true"/>
<XCUIElementTypeStaticText label="¥899" x="200" y="330" width="60" height="20" visible="true"/>
<XCUIElementTypeStaticText label="hidden" visible="false"/>
</XCUIElementTypeCell>
<XCUIElementTypeButton name="立即购买" visible="true"/>
</XCUIElementTypeCollectionView></XCUIElementTypeApplication></AppiumAUT>"""


def test_android_cards():
    assert android_cards(ANDROID) == [("Timberland Martin boot|¥512", 60, 780), ("Nike Dunk Low|¥899", 600, 780)]


def test_android_texts_include_content_desc():
    assert android_texts(ANDROID)[-1] == "立即购买"


def test_ios_cards():
    assert ios_cards(IOS) == [("Timberland Martin boot|¥512", 40, 340), ("Nike Dunk Low|¥899", 230, 340)]


def test_ios_texts():
    assert ios_texts(IOS) == ["Timberland Martin boot", "¥512", "Nike Dunk Low", "¥899", "立即购买"]


def test_android_adapter_calls_real_uiautomator2_api():
    """Every call AndroidDevice makes must exist with these arguments in the installed uiautomator2:
    a spec'd mock raises on unknown methods and wrong signatures."""
    import pytest
    from unittest import mock
    u2 = pytest.importorskip("uiautomator2")
    from poizon.devices import AndroidDevice

    d = mock.create_autospec(u2.Device, instance=True)
    d.dump_hierarchy.return_value = ANDROID
    d.app_list.return_value = ["com.shizhuang.duapp"]
    d.app_current.return_value = {"package": "com.shizhuang.duapp", "activity": "x"}
    with mock.patch.object(u2, "connect", return_value=d):
        dev = AndroidDevice()
    assert dev.texts()[0] == "Timberland Martin boot"
    assert dev.installed("com.shizhuang.duapp")
    assert dev.foreground() == "com.shizhuang.duapp"
    dev.tap(10, 20)
    dev.back()
    dev.screenshot("/tmp/x.png")
    d.click.assert_called_once_with(10, 20)
    d.press.assert_called_once_with("back")
    d.app_current.side_effect = RuntimeError("screen off")
    assert dev.foreground() is None


def test_ios_adapter_options_are_real_appium_capabilities():
    import pytest
    pytest.importorskip("appium")
    from unittest import mock
    from appium import webdriver
    from poizon.devices import IOSDevice

    remote = mock.MagicMock()
    remote.get_window_size.return_value = {"width": 390, "height": 844}
    with mock.patch.object(webdriver, "Remote", return_value=remote) as cls:
        dev = IOSDevice("UDID-1", team_id="TEAM", wda_bundle_id="com.me.wda")
    caps = cls.call_args.kwargs["options"].to_capabilities()
    assert caps["appium:udid"] == "UDID-1" and caps["appium:noReset"] is True
    assert caps["appium:xcodeOrgId"] == "TEAM" and caps["appium:updatedWDABundleId"] == "com.me.wda"
    assert (dev.w, dev.h) == (390, 844)
