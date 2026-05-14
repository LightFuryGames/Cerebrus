"""S3 uploader plugin package."""

__all__ = [
    "S3UploaderPlugin",
    "_derive_s3_dir_from_metadata",
    "_extract_report_metadata",
    "_strip_raw_csv_tab_from_report",
    "_upload_file_to_s3",
]


def __getattr__(name: str):
    if name in __all__:
        from cerebrus.plugins.s3_uploader import plugin

        return getattr(plugin, name)
    raise AttributeError(name)
