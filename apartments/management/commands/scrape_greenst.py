from __future__ import annotations

import os
import tempfile
from django.core.management.base import BaseCommand

from apartments.scraping import run_greenst_scrape
from apartments.scrape_ingest import ingest_greenst_jsonl


class Command(BaseCommand):
    help = "Scrape Green Street Realty and ingest results into the database."

    def handle(self, *args, **options):
        fd, path = tempfile.mkstemp(prefix="greenst_", suffix=".jsonl")
        os.close(fd)

        try:
            self.stdout.write(f"Running Scrapy -> {path}")
            run_greenst_scrape(output_jsonl_path=path, log_level="INFO")

            self.stdout.write("Ingesting into DB...")
            n = ingest_greenst_jsonl(path)
            self.stdout.write(self.style.SUCCESS(f"Done. Records processed: {n}"))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass