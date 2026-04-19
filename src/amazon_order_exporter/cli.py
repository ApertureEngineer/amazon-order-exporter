from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from .exporter import write_outputs
from .scraper import AmazonScraper, ScrapeConfig


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def valid_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Ungültiges Datum: {value}. Erwartet wird YYYY-MM-DD.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amazon-order-exporter")
    parser.add_argument("--verbose", action="store_true", help="Mehr Logging ausgeben")

    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Amazon-Session lokal speichern")
    login_parser.add_argument("--domain", default="amazon.de")
    login_parser.add_argument("--auth-file", default=".secrets/amazon_state.json")
    login_parser.add_argument("--headless", action="store_true", help="Browser headless starten")
    login_parser.add_argument("--slow-mo-ms", type=int, default=50)

    export_parser = subparsers.add_parser("export", help="Bestellungen und Artikel exportieren")
    export_parser.add_argument("--domain", default="amazon.de")
    export_parser.add_argument("--auth-file", default=".secrets/amazon_state.json")
    export_parser.add_argument("--output", default="data/output/amazon_orders.xlsx")
    export_parser.add_argument("--year", type=int)
    export_parser.add_argument("--date-from", type=valid_date)
    export_parser.add_argument("--date-to", type=valid_date)
    export_parser.add_argument("--max-pages", type=int, default=25)
    export_parser.add_argument("--headless", action="store_true")
    export_parser.add_argument("--slow-mo-ms", type=int, default=50)
    export_parser.add_argument("--timeout-ms", type=int, default=30000)
    export_parser.add_argument("--debug-dir", default="data/output/debug")

    return parser


def resolve_date_range(args: argparse.Namespace) -> tuple[date | None, date | None]:
    if args.year:
        return date(args.year, 1, 1), date(args.year, 12, 31)
    return args.date_from, args.date_to


def run_login(args: argparse.Namespace) -> int:
    config = ScrapeConfig(
        domain=args.domain,
        auth_file=Path(args.auth_file),
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
    )
    with AmazonScraper(config) as scraper:
        scraper.login_and_save_session()
    return 0


def run_export(args: argparse.Namespace) -> int:
    date_from, date_to = resolve_date_range(args)
    if date_from and date_to and date_from > date_to:
        raise SystemExit("date-from darf nicht nach date-to liegen.")

    auth_file = Path(args.auth_file)
    if not auth_file.exists():
        raise SystemExit(f"Session-Datei fehlt: {auth_file}. Bitte zuerst 'amazon-order-exporter login' ausführen.")

    config = ScrapeConfig(
        domain=args.domain,
        auth_file=auth_file,
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
    )

    with AmazonScraper(config) as scraper:
        orders = scraper.scrape_orders(
            date_from=date_from,
            date_to=date_to,
            max_pages=args.max_pages,
            target_year=args.year,
        )
        items = scraper.scrape_items_for_orders(orders)

    paths = write_outputs(orders=orders, items=items, output_path=Path(args.output))

    print(f"Excel: {paths.xlsx_path}")
    print(f"Orders CSV: {paths.orders_csv_path}")
    print(f"Items CSV: {paths.items_csv_path}")
    print(f"Orders: {len(orders)}")
    print(f"Items: {len(items)}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)

    if args.command == "login":
        return run_login(args)
    if args.command == "export":
        return run_export(args)

    raise SystemExit(f"Unbekannter Befehl: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
