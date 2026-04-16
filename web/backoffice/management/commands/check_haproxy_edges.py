from __future__ import annotations

import socket
from typing import Any

from django.core.management.base import BaseCommand
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from cabinet.models import EdgeServer


class Command(BaseCommand):
    help = "Refresh health snapshots for HAProxy edge inventory."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--timeout", type=float, default=2.5, help="TCP connect timeout in seconds.")

    def handle(self, *args: Any, **options: Any) -> None:
        timeout = float(options["timeout"])
        now = timezone.now()
        try:
            edges = list(EdgeServer.objects.order_by("priority", "id"))
        except (OperationalError, ProgrammingError) as exc:
            self.stderr.write(self.style.ERROR(f"Edge inventory is unavailable: {exc}"))
            return

        if not edges:
            self.stdout.write("No HAProxy edges configured.")
            return

        for edge in edges:
            host = str(getattr(edge, "healthcheck_host", "") or getattr(edge, "public_ip", "") or getattr(edge, "public_host", "")).strip()
            port = int(getattr(edge, "healthcheck_port", None) or getattr(edge, "frontend_port", 0) or 0)
            payload: dict[str, Any] = {
                "last_health_at": now,
                "updated_at": now,
            }
            label = f"{edge.name} ({host}:{port})"

            if not edge.is_active:
                payload["last_health_ok"] = None
                payload["last_health_error"] = "inactive"
                EdgeServer.objects.filter(pk=edge.pk).update(**payload)
                self.stdout.write(f"{label}: skipped inactive")
                continue

            if not host or port <= 0:
                payload["last_health_ok"] = False
                payload["last_health_error"] = "missing healthcheck endpoint"
                EdgeServer.objects.filter(pk=edge.pk).update(**payload)
                self.stdout.write(self.style.WARNING(f"{label}: invalid healthcheck endpoint"))
                continue

            try:
                with socket.create_connection((host, port), timeout=timeout):
                    payload["last_health_ok"] = True
                    payload["last_health_error"] = ""
                    self.stdout.write(self.style.SUCCESS(f"{label}: healthy"))
            except OSError as exc:
                payload["last_health_ok"] = False
                payload["last_health_error"] = str(exc)
                self.stdout.write(self.style.WARNING(f"{label}: {exc}"))

            EdgeServer.objects.filter(pk=edge.pk).update(**payload)
