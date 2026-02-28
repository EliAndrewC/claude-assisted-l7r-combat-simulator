# L7R Combat Simulator

## Development

```bash
podman run --interactive --tty --rm \
  --name claude-assisted \
  --user 1001:1001 \
  --userns keep-id \
  --env HOME=/home/user \
  --tmpfs /home/user:rw \
  --volume "$(pwd)":/workspace \
  --workdir /workspace \
  --publish 8503:8501 \
  docker.io/docker/sandbox-templates:claude-code \
  bash
```

or on Docker:

```
docker run -it --rm --name claude-assisted -v "$(pwd):/workspace" -p 8503:8501 claude-code-sandbox:latest bash
```
