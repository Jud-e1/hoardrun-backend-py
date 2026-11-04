release: cd fintech_backend && python -m app.database.migrate upgrade
web: cd fintech_backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips="*" --timeout-keep-alive 15 --no-server-header
