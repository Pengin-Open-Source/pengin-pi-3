from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        from util.macros_patch import patch_macros_node_mutation_bug
        patch_macros_node_mutation_bug()
