"""Entry point: python -m ikarus [--port 8080] [--situation cruise|runway]"""

import argparse

from ikarus.net import server


def main() -> None:
    parser = argparse.ArgumentParser(prog="ikarus", description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--situation", default="cruise",
                        choices=("cruise", "runway", "cold_dark"))
    args = parser.parse_args()
    server.run(situation=args.situation, port=args.port)


if __name__ == "__main__":
    main()
