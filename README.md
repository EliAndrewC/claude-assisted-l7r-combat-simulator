# L7R Combat Simulator

## Development

```bash
podman run --interactive --tty --rm \
  --name claude-assisted \
  --userns keep-id \
  --user 1000:1000 \
  --volume "$(pwd)":/home/agent/workspace/l7r \
  --publish 8503:8501 \
  docker.io/docker/sandbox-templates:claude-code \
  bash
```

or on Docker:

```
docker run -it --rm --name claude-assisted -v "$(pwd):/workspace" -p 8503:8501 claude-code-sandbox:latest bash
```
