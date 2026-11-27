# matlab-shell

基于 `uv` + Python 的终端交互式 MATLAB CLI 项目。

## 环境约定

- 本机目标环境：MATLAB R2026a（`26.1`），`matlabengine` 官方支持 Python 3.9–3.13；本项目默认使用 Python 3.12。
- 使用 `uv` 管理虚拟环境与依赖，避免误用系统默认的不兼容 Python 版本。

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues (`muzijin701/matlab-shell`) via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`GLOSSARY.md` and `docs/adr/` created lazily). See `docs/agents/domain.md`.
