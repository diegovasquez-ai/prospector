#!/bin/sh
# Lo tuyo (prospectos, borradores, sesiones de WhatsApp, negocio.md, firma...) vive en
# /data, el volumen persistente. Aquí se enlaza a donde el programa lo busca, para que
# sobreviva a cada deploy.
set -e
mkdir -p /data
for carpeta in datos fichas borradores .whatsapp; do
  mkdir -p "/data/$carpeta"
  rm -rf "/app/$carpeta"
  ln -s "/data/$carpeta" "/app/$carpeta"
done
for archivo in .env negocio.md nicho.json firma.txt comunas.txt; do
  # La primera vez parte de la semilla del repo; después manda lo que edites en /data.
  if [ ! -e "/data/$archivo" ] && [ -f "/app/semilla/$archivo" ]; then
    cp "/app/semilla/$archivo" "/data/$archivo"
  fi
  rm -f "/app/$archivo"
  ln -s "/data/$archivo" "/app/$archivo"
done
# Sin el .env no pasa nada: las claves pueden venir de las variables de entorno de Coolify.
[ -f /data/.env ] || : > /data/.env
exec "$@"
