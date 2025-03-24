from django.apps import AppConfig
import pickle

class SearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "search"

    # def ready(self) -> None:
