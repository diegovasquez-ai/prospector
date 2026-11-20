# Prospector · prospección en frío, para un servidor (Coolify o cualquier Docker).
#
# Un solo contenedor: el panel (Python), el envío de correos y WhatsApp, el puente de
# WhatsApp (Node) y Claude Code para investigar. Todo lo tuyo vive en /data: monta ahí
# un volumen persistente o lo pierdes en cada deploy.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=America/Santiago \
    PANEL_PUERTO=8765

# Node 22 para el puente de WhatsApp y Claude Code; tzdata para que el horario de envío sea el de Chile.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg tzdata \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @anthropic-ai/claude-code \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY whatsapp/package.json whatsapp/
RUN cd whatsapp && npm install --omit=dev --no-fund --no-audit

COPY . .
RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod +x docker/entrypoint.sh

VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fs http://127.0.0.1:8765/salud || exit 1
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["python", "prospector.py", "panel", "--host", "0.0.0.0", "--puerto", "8765", "--sin-navegador"]
