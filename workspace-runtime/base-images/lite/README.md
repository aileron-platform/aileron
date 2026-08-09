# workspace-runtime base-lite

`base-lite` 是 `workspace-runtime` 的精簡 base image。

## 內容

- 主要 CLI：`git`、`git-lfs`、`curl`、`wget`、`jq`、`ripgrep`、`fd`、`make`、`rsync`、`zip`、`unzip`、`ssh`
- Python 3
- `uv`
- Node.js 22
- Go 1.23.x
- OpenJDK 21

## Build

```bash
docker build -t ailerondocker/workspace-runtime-base-lite:custom ./workspace-runtime/base-images/lite
```

之後可配合 `workspace-runtime` build：

```bash
make build-workspace-runtime
```
