#!/bin/bash

PROFILE="ocr-env"
SOCKET="$HOME/.colima/$PROFILE/docker.sock"

# 1. Iniciar el perfil si no está corriendo
if ! colima list | grep "$PROFILE" | grep -q Running; then
  echo "Iniciando perfil $PROFILE..."
  colima start --profile "$PROFILE" --cpu 4 --memory 6 --disk 60 --runtime docker
else
  echo "Perfil $PROFILE ya está activo."
fi

# 2. Apuntar el Docker CLI a este perfil
export DOCKER_HOST=unix://$SOCKET
echo "Docker apuntando a $PROFILE"

# 3. Verificar que Docker funcione
if ! docker info > /dev/null 2>&1; then
  echo "Error: No se pudo conectar al Docker de $PROFILE"
  exit 1
fi

# 4. Levantar los servicios con Docker Compose
echo "Levantando servicios con docker-compose..."
docker compose up --build