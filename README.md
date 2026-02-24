# L7R Combat Simulator

## Development

```bash
podman run --interactive --tty --rm \
  --name claude-assisted \
  --userns keep-id \
  --user "$(id -u):$(id -g)" \
  --volume "$(pwd)":/home/agent/workspace/l7r \
  --publish 8503:8501 \
  docker.io/docker/sandbox-templates:claude-code \
  bash
```

or

```
docker run -it --rm --name claude-assisted -v "$(pwd):/workspace" -p 8503:8501 claude-code-sandbox:latest bash
```
