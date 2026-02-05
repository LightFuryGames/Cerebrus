"""Module entry point for launching the Cerebrus UI."""

from cerebrus.ui import CerebrusApp


def main() -> None:
    app = CerebrusApp()
    app.run()


if __name__ == "__main__":
    main()
