import multiprocessing

# Número de workers
workers = multiprocessing.cpu_count() * 2 + 1

# Timeouts
timeout = 120  # 120 segundos
keepalive = 5

# Logs
accesslog = "-"
errorlog = "-"