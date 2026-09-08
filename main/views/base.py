from django.views import View

from util.mixins import RedisLoggingMixin


class SuperTemplateView(RedisLoggingMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.log_request(request)
        return super().dispatch(request, *args, **kwargs)
