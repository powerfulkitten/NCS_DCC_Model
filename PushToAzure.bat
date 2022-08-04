@ECHO ON
docker login tapp0316.azurecr.io -u tapp0316 -p VuCODQZjWx+kKnycLvQdBgPQY9/8j28z
docker buildx build -f Dockerfile.amd64 -t tapp0316.azurecr.io/dcc-amd64 --platform linux/amd64 . --push
docker buildx build -f Dockerfile.arm64v8 -t tapp0316.azurecr.io/dcc-arm64 --platform linux/arm64 . --push
docker manifest create tapp0316.azurecr.io/dcc tapp0316.azurecr.io/dcc-amd64 tapp0316.azurecr.io/dcc-arm64
docker manifest push --purge tapp0316.azurecr.io/dcc
docker logout tapp0316.azurecr.io