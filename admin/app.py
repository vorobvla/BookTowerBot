"""Main application class for the Admin console."""

from typing import Optional

from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.router import AdminRouter
from admin.server.server import AdminServer
from admin.services.map_service import AdminMapService
from admin.services.recs_service import AdminRecsService
from admin.services.timetable_service import AdminTimetableService


class AdminApp:
    """Encapsulates and runs the complete Admin Web Application."""

    def __init__(self, config: Optional[AdminConfig] = None):
        self.config = config or AdminConfig.from_env()
        self.session_manager = AdminSessionManager(self.config.session_timeout_seconds)
        self.authenticator = AdminAuthenticator(self.config)
        self.recs_service = AdminRecsService(self.config.recs_path)
        self.timetable_service = AdminTimetableService(self.config.timetables_path)
        self.map_service = AdminMapService(self.config.map_dir)

        self.router = AdminRouter(
            config=self.config,
            authenticator=self.authenticator,
            session_manager=self.session_manager,
            recs_service=self.recs_service,
            timetable_service=self.timetable_service,
            map_service=self.map_service,
        )

        self.server = AdminServer(router=self.router, config=self.config)

    def run(self, background: bool = False) -> None:
        """Run the admin application server."""
        self.server.start(background=background)

    def stop(self) -> None:
        """Stop the admin application server."""
        self.server.stop()
