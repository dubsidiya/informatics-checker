# Развёртывание Informatics Checker

## Сервер

- Провайдер: Timeweb Cloud
- ОС: Ubuntu 26.04 LTS
- Ресурсы: 4 vCPU, 8 GB RAM, примерно 80 GB NVMe
- Адрес: `http://129.101.115.158`
- Render не используется

## Расположение

- Код приложения: `/opt/informatics-checker`
- Виртуальное окружение: `/opt/informatics-checker/.venv`
- База данных: `/var/lib/informatics-checker/checker.sqlite3`
- Переменные окружения: `/etc/informatics-checker.env`
- Systemd unit: `/etc/systemd/system/informatics-checker.service`
- Nginx config: `/etc/nginx/sites-available/informatics-checker`
- Системный пользователь: `checker`

## Управление приложением

```bash
systemctl status informatics-checker
systemctl restart informatics-checker
systemctl stop informatics-checker
systemctl start informatics-checker
journalctl -u informatics-checker -f
```

Проверка доступности:

```bash
curl http://127.0.0.1/health
curl http://129.101.115.158/health
```

Проверка Nginx:

```bash
nginx -t
systemctl reload nginx
```

## Обновление из GitHub

Выполнять от root или пользователя с правами на каталог:

```bash
cd /opt/informatics-checker
git fetch origin
git reset --hard origin/main
chown -R checker:checker /opt/informatics-checker
systemctl restart informatics-checker
```

Если изменились зависимости:

```bash
/opt/informatics-checker/.venv/bin/python -m pip install -r requirements.txt
```

## Безопасность

- Вход по SSH-паролю отключён.
- Доступ по SSH выполняется только ключом.
- Firewall разрешает только порты `22/tcp` и `80/tcp`.
- Код учеников запускается локальным sandbox-раннером приложения.
- Root-пароль и приватный SSH-ключ не должны храниться в Git или этом файле.
- PIN учителя хранится только в `/etc/informatics-checker.env` в виде `TEACHER_PIN_HASH`.

## Резервное копирование

Минимальная ручная копия базы:

```bash
install -d -m 700 /root/backups/informatics-checker
BACKUP="/root/backups/informatics-checker/checker-$(date +%F-%H%M).sqlite3"
/opt/informatics-checker/.venv/bin/python - "$BACKUP" <<'PY'
import sqlite3
import sys

source = sqlite3.connect("/var/lib/informatics-checker/checker.sqlite3")
target = sqlite3.connect(sys.argv[1])
with target:
    source.backup(target)
target.close()
source.close()
PY
```

Копии нужно регулярно переносить за пределы сервера. Если сервер выйдет из строя, локальная копия на том же диске не поможет.

## После изменений

```bash
cd /opt/informatics-checker
/opt/informatics-checker/.venv/bin/python -m compileall -q checker app.py
systemctl restart informatics-checker
curl -fsS http://127.0.0.1/health
```
