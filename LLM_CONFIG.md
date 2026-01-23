# LLM 配置说明（llm.json）

本项目的第二阶段（`phase2_analysis/run_phase2.py`）会读取根目录的 `llm.json` 来决定：

- 调用哪个 Provider（例如：火山方舟）
- 具体使用哪个模型（model id）
- 以及调用参数（例如：temperature、max_tokens 等）

建议优先使用 `profiles` 来管理多模型/多参数场景。

## 配置文件位置

- 默认：根目录 `llm.json`
- 可通过命令行覆盖：`python phase2_analysis/run_phase2.py ... --llm-config path/to/llm.json`

## 顶层字段

### `providers`（必填）

Provider 配置字典：`{ "<provider_name>": <provider_config> }`

示例：

```json
{
  "providers": {
    "volc_doubao": {
      "type": "volc_ark",
      "base_url": "https://ark.cn-beijing.volces.com",
      "api_key": "VOLC_ARK_API_KEY",
      "model": "doubao-seed-1-8-251228"
    }
  }
}
```

### `profiles`（推荐）

Profile 用来把“provider + model + params”打包成一个可选项：`{ "<profile_name>": <profile_config> }`

当 `llm.json` 里模型多了之后，建议每个使用场景（例如 phase2）固定一个 profile 名称，然后只切 profile。

### `default_profile`（推荐）

指定默认使用的 profile 名称（字符串）。未传 `--profile` 时会使用它。

### `default_provider`（可选）

当未使用 profiles 或 profile 未指定 provider 时，作为 provider 的兜底选择。

如果不配置该字段，程序会默认取 `providers` 里的第一个 provider。

## `providers.<provider_name>` 字段

以 `providers.volc_doubao` 为例：

### `type`（必填）

Provider 类型。

当前代码仅实现：

- `volc_ark`：火山方舟 Chat Completions

### `base_url`（必填）

API Base URL，例如：

- `https://ark.cn-beijing.volces.com`

（脚本会自动补齐 `/api/v3/chat/completions` 路径）

### `api_key`（必填）

两种写法都支持：

1) 直接写 key（不推荐把密钥写进仓库）
2) 写“环境变量名”（推荐）

例如：

```json
{ "api_key": "VOLC_ARK_API_KEY" }
```

运行前设置环境变量：

- Windows PowerShell：`$env:VOLC_ARK_API_KEY="你的key"`
- Linux/macOS：`export VOLC_ARK_API_KEY="你的key"`

解析规则：

- 如果 `api_key` 的值在环境变量中存在同名变量，则优先使用环境变量的值
- 否则把 `api_key` 当作“直接 key”使用

### `model`（可选，但建议配置）

该 provider 的默认模型 ID（用于兼容不使用 profiles 的旧用法，或 profile 未指定 model 时作为兜底）。

## `profiles.<profile_name>` 字段

以 `profiles.phase2_doubao` 为例：

### `provider`（必填）

引用 `providers` 里的某个 provider 名称，例如：`"volc_doubao"`。

### `model`（必填）

本 profile 使用的模型 ID（优先级高于 `providers.<provider>.model`）。

### `params`（可选）

模型调用参数对象（不填则使用默认值）。

支持字段：

- `temperature`（float，默认 0.2）
- `max_tokens`（int，默认 10000）
- `timeout_s`（int，默认 120）
- `thinking`（object，默认 `{"type":"disabled"}`，会原样传给火山方舟接口）

示例：

```json
{
  "profiles": {
    "phase2_doubao": {
      "provider": "volc_doubao",
      "model": "doubao-seed-1-8-251228",
      "params": {
        "temperature": 0.2,
        "max_tokens": 10000,
        "timeout_s": 120,
        "thinking": { "type": "disabled" }
      }
    }
  }
}
```

## 命令行覆盖（Phase2）

运行 `phase2_analysis/run_phase2.py` 时可覆盖选择逻辑：

- `--profile <name>`：指定使用哪个 profile（推荐）
- `--provider <name>`：覆盖 provider（不常用）
- `--model <model_id>`：覆盖模型 ID（不常用）
- `--temperature <float>`：覆盖温度
- `--max-tokens <int>`：覆盖 max_tokens

示例：

```powershell
python phase2_analysis/run_phase2.py "book/书名" --profile phase2_doubao_creative
```
