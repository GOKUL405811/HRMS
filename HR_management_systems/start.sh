#!/bin/bash
python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn HR_management_systems.wsgi
