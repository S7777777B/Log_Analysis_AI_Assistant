#!/usr/bin/env python3
# simulate_logs.py
import time
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os

LOG_DIR = "./sample_logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_CONFIG = {
    "vpn": "vpn.log",
    "oa": "oa.log",
    "api": "api.log",
    "system": "system.log"
}

USERS = ["zhangwei", "lili", "wangqiang", "admin", "liujie", "zhaoyun"]
IP_POOL = [f"192.168.1.{i}" for i in range(10, 30)] + [f"10.0.0.{i}" for i in range(5, 15)]

def get_logger(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    return logger

loggers = {t: get_logger(t, f) for t, f in LOG_CONFIG.items()}

def vpn_log():
    user = random.choice(USERS)
    ip = random.choice(IP_POOL)
    action = random.choice(["login", "logout", "login_failed"])
    ts = datetime.now().isoformat()
    if action == "login_failed":
        reason = random.choice(["wrong_pwd", "expired", "ip_deny"])
        return f"{ts} [VPN] user={user} src_ip={ip} action={action} reason={reason}"
    return f"{ts} [VPN] user={user} src_ip={ip} action={action}"

def oa_log():
    user = random.choice(USERS)
    ops = ["approve", "reject", "clock_in", "upload", "download"]
    act = random.choice(ops)
    ts = datetime.now().isoformat()
    return f"{ts} [OA] user={user} action={act}"

def api_log():
    endpoints = ["/api/login", "/api/users", "/api/export", "/api/report"]
    method = random.choice(["GET", "POST"])
    ep = random.choice(endpoints)
    status = random.choices([200, 400, 401, 500], weights=[0.8,0.05,0.1,0.05])[0]
    user = random.choice(USERS)
    ts = datetime.now().isoformat()
    return f"{ts} [API] method={method} endpoint={ep} user={user} status={status}"

def system_log():
    events = ["cpu_high", "mem_critical", "service_start", "service_stop"]
    ev = random.choice(events)
    ts = datetime.now().isoformat()
    if ev in ["cpu_high", "mem_critical"]:
        val = random.randint(85, 98)
        return f"{ts} [SYS] event={ev} usage={val}%"
    svc = random.choice(["nginx", "mysql", "filebeat"])
    return f"{ts} [SYS] event={ev} service={svc}"

def main():
    print(f"日志生成中，目录: {LOG_DIR}")
    while True:
        typ = random.choice(list(LOG_CONFIG.keys()))
        if typ == "vpn":
            line = vpn_log()
        elif typ == "oa":
            line = oa_log()
        elif typ == "api":
            line = api_log()
        else:
            line = system_log()
        loggers[typ].info(line)
        time.sleep(random.uniform(0.1, 0.5))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("停止生成")