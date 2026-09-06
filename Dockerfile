# Imagen de la demo web del Estudio 1.
#
# El contexto de build es la RAÍZ del repo, no web/: el contenedor necesita
# protocolo/ (el contenido del experimento) y comun/ (el cargador y el agente)
# además del servidor.
#
# No hay pip install: el servidor es sólo biblioteca estándar.

FROM python:3.11-slim

WORKDIR /app

COPY protocolo/ ./protocolo/
COPY comun/ ./comun/
COPY web/ ./web/

ENV PUERTO=8080 \
    CARPETA_DATOS=/datos \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "-m", "web.servidor.app"]
