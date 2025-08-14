import subprocess
import sys
from aletk.utils import get_logger

lgr = get_logger(__name__)


def main() -> None:
    try:
        # Run autoflake to remove unused imports
        lgr.info("Running autoflake to remove unused imports...")
        subprocess.run(
            ["autoflake", "--in-place", "--remove-all-unused-imports", "--recursive", "--verbose", "."], check=True
        )
        lgr.info("Successfully removed unused imports.")

        lgr.info("Running black to format the code...")
        # Run black to format the code
        subprocess.run(["black", "."], check=True)
        lgr.info("Successfully formatted the code with black.")

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
