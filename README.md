# devops_bot

Проект состоит из двух веток:

- `docker` — запуск проекта в контейнерах
- `ansible` — развертывание без контейнеров на 3 ВМ через Ansible

## Ветка docker


### Настройка .env

Файла `.env` нет. Его нужно создать его рядом с `docker-compose.yaml`.

Пример `.env`:

```
TOKEN=PASTE_TELEGRAM_BOT_TOKEN
DB_NAME=db_customers
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432
```

### Запуск

Надо перейти на ветку `docker`:

```bash
git checkout docker
```

### Запуск:

```bash
docker compose --env-file .env up --build
```

### Остановка

```bash
docker compose --env-file .env down -v
```

## Ветка ansible

Развертывание на 3х ВМ через ansible:
- VM1: PostgreSQL primary
- VM2: PostgreSQL replica
- VM3: Telegram bot как systemd-сервис

### Требования

На машине, с которой запускается Ansible:

- Ansible
- SSH доступ на 3 ВМ
- Пользователь на ВМ имеет sudo

На 3х ВМ:

- Ubuntu/Debian
- Могут достучаться до друг друга (primary стучиться до replica по порту 5432)
- systemd на bot-ВМ

### Подготовка 3 ВМ

1) Сначала надо убедиться, что вы можете подключиться по SSH:

```bash
ssh <логин>@<IP>
```

2) Потом надо проверить, что Ansible видит хосты:

```bash
ansible -i ansible/inventory all -m ping
```

Если есть ошибки `Host key verification failed` — надо удалить ключи и добавить их заново:

```bash
ssh-keygen -R <IP>
ssh-keyscan -H <IP> >> ~/.ssh/known_hosts
```

### Настройка inventory

Переходим на ветку `ansible`:

```bash
git checkout ansible
```

Не забудьте исправить `ansible/inventory`. Надо указать IP и пользователей. Пример:

```
[db_primary]
db-primary ansible_host=192.168.136.151 ansible_user=smirnov

[db_replica]
db-replica ansible_host=192.168.136.152 ansible_user=smirnov

[bot]
tg-bot ansible_host=192.168.136.153 ansible_user=smirnov
```

Шаблон
```
[db_primary]
db-primary ansible_host=<ip_vm1> ansible_user=<login_vm1>

[db_replica]
db-replica ansible_host=<ip_vm2> ansible_user=<login_vm2>

[bot]
tg-bot ansible_host=<ip_vm3> ansible_user=<login_vm3>
```

### Запуск playbook

```bash
ansible-playbook -i ansible/inventory ansible/playbook_tg_bot.yml --ask-become-pass -e repo_url=https://github.com/terribleMOTHMAN/devops_bot.git -e bot_token=<TOKEN>
```


