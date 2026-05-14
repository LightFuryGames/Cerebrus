from pathlib import Path


def test_pyinstaller_spec_bundles_plugin_resources():
    spec_text = Path("scripts/cerebrus.spec").read_text()

    assert 'plugins_dir = cerebrus_dir / "plugins"' in spec_text
    assert "plugins_dir.rglob('*')" in spec_text
    assert "cerebrus/plugins/{rel_path.parent}" in spec_text


def test_pyinstaller_spec_keeps_boto3_botocore_data_files():
    spec_text = Path("scripts/cerebrus.spec").read_text()

    assert "collect_data_files('boto3')" in spec_text
    assert "collect_data_files('botocore')" in spec_text
    assert "'boto3'" in spec_text
    assert "'botocore'" in spec_text
