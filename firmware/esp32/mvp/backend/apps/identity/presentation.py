from django.conf import settings


def mode_context(request):
    return {'ogpass_mode': settings.OGPASS_MODE,
            'developer_mode': settings.OGPASS_MODE == 'developer' and request.user.is_staff}

