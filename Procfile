web: gunicorn dvctracker:app --log-file -
scheduler: yacron -c schedule.yml
release: flask deploy
