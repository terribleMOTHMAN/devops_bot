FROM postgres:16
COPY init.sql /docker-entrypoint-initdb.d/init.sql
COPY --chmod=755 init.sh /docker-entrypoint-initdb.d/init.sh
