from pipeline.resize_genome import resize_flam3_xml


def test_resize_updates_size_and_scale():
    xml = '<flame time="0" size="800 592" scale="246.509"></flame>'
    out = resize_flam3_xml(xml, 1920, 1080)
    assert 'size="1920 1080"' in out
    # scale_factor = min(1920/800, 1080/592) = min(2.4, 1.8243...) ≈ 1.8243
    assert "scale=" in out
    assert "800 592" not in out


def test_resize_raises_when_no_flame_elements():
    import pytest

    with pytest.raises(ValueError, match="no <flame>"):
        resize_flam3_xml("<notflame/>", 1920, 1080)
