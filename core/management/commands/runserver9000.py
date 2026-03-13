"""
Custom management command: `python manage.py runserver9000`

Starts the development server on 127.0.0.1:9000 by default so that
`python manage.py runserver` on port 8000 (occupied) is never used accidentally.
"""
from django.contrib.staticfiles.management.commands.runserver import Command as RunserverCommand


class Command(RunserverCommand):
    help = "Start the dev server on 127.0.0.1:9000 (EIAnalysis default)."

    default_addr = '127.0.0.1'
    default_port = '9000'
