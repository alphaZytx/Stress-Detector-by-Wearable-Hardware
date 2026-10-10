from stress_detection.config import get_config


def test_package_imports():
    import stress_detection  # noqa: F401


def test_config_loads():
    cfg = get_config()
    assert cfg.windowing.window_s == 30
    assert cfg.windowing.stride_s == 5
    assert cfg.random_seed == 42
    assert cfg.sampling.sensors_hz == 1
    assert cfg.paths.data_raw.name == "raw"
