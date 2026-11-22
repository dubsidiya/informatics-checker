# Развёртывание Informatics Checker

## Сервер

- ОС: Ubuntu 24.04 LTS
- Ресурсы: 2 vCPU, 4 GB RAM, примерно 69 GB диска
- Адрес: `http://77.90.25.82`
- Python: 3.13
- Приложение слушает только `127.0.0.1:8765`, снаружи открыт порт 80 через Nginx

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
curl http://77.90.25.82/health
```

Проверка Nginx:

```bash
nginx -t
systemctl reload nginx
```

## Обновление из GitHub

Одна команда на сервере от root:

```bash
bash /opt/informatics-checker/deploy/update.sh
```

Скрипт тянет `origin/main`, обновляет зависимости, компилирует код,
перезапускает `informatics-checker` и проверяет `/health`. Если сервис не
ответил, он сам покажет хвост журнала и завершится с ошибкой.

Перед рискованным обновлением (миграции базы) сделай копию:

```bash
bash /opt/informatics-checker/deploy/update.sh --backup
```

Откат на предыдущий коммит:

```bash
bash /opt/informatics-checker/deploy/update.sh --rollback
```

Скрипт `deploy/update.py` не трогает базу в `/var/lib/informatics-checker`.

## Безопасность

- Firewall разрешает только порты `22/tcp` и `80/tcp`.
- Вход по SSH пока по паролю. Пароль и пин учителя в git не хранятся.
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

## Наводки MiMo на Mac

Модель крутится на Mac учителя, не на сервере. Проверяльщик на сервере ходит к ней через SSH-туннель. Пока туннель или модель молчат, ученик получает обычный разбор автотестов, вердикт от модели не зависит.

На Mac один раз. `ollama pull` с Hugging Face здесь обрывается, файл качается напрямую, около 5.8 GB:

```bash
brew install ollama
brew services start ollama
mkdir -p "$HOME/Library/Application Support/informatics-checker"
curl -L --fail --retry 8 -C - \
  -o "$HOME/Library/Application Support/informatics-checker/MiMo-V2.6-Distill-Qwen-9B-Q4_K_M.gguf" \
  "https://huggingface.co/bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF/resolve/main/MiMo-V2.6-Distill-Qwen-9B-Q4_K_M.gguf"
cat > /tmp/mimo.Modelfile <<EOF
FROM $HOME/Library/Application Support/informatics-checker/MiMo-V2.6-Distill-Qwen-9B-Q4_K_M.gguf
PARAMETER temperature 0.2
PARAMETER num_ctx 8192
EOF
ollama create mimo-v2.6 -f /tmp/mimo.Modelfile
```

Токен шлюза лежит только на Mac в `secrets/mimo.env` (файл в gitignore) и копируется в `/etc/informatics-checker.env` на сервере как `LLM_TOKEN`. Шлюз слушает `127.0.0.1:8788` и пускает только `/api/chat`.

```bash
set -a; source secrets/mimo.env; set +a
python -m checker.llm_gateway
ssh -N -R 127.0.0.1:8788:127.0.0.1:8788 root@77.90.25.82
```

На сервере в `/etc/informatics-checker.env`:

```bash
LLM_URL=http://127.0.0.1:8788
LLM_MODEL=mimo-v2.6
LLM_TOKEN=тот же токен, что на Mac
```

После правки env: `systemctl restart informatics-checker`. Mac при этом должен быть включён, шлюз и туннель — запущены.

## После изменений

```bash
cd /opt/informatics-checker
/opt/informatics-checker/.venv/bin/python -m compileall -q checker app.py
systemctl restart informatics-checker
curl -fsS http://127.0.0.1/health
```
