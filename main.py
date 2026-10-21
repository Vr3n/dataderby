"""Project entry point."""

from collections.abc import Sequence

from dataderby.fixtures.cli import main


def run(argv: Sequence[str] | None = None) -> int:
    """Run the project's command line interface.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(run())
