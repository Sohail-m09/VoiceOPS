import voiceops


def test_package_exposes_a_version():
    assert isinstance(voiceops.__version__, str)
    assert voiceops.__version__
