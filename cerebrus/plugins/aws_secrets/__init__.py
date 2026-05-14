"""AWS Secrets plugin package."""

__all__ = ["AWSSecretsManager", "AWSSecretsPlugin"]


def __getattr__(name: str):
    if name in __all__:
        from cerebrus.plugins.aws_secrets.plugin import (
            AWSSecretsManager,
            AWSSecretsPlugin,
        )

        return {
            "AWSSecretsManager": AWSSecretsManager,
            "AWSSecretsPlugin": AWSSecretsPlugin,
        }[name]
    raise AttributeError(name)
