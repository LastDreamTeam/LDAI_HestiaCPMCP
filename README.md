# HestiaCP 网站管理 MCP

> **自用项目** · 本仓库主要供维护者自用。

使用自选面板的 HestiaCP 原生 REST API 查询网站、DNS、数据库和备份，按明确的域名创建网站。

## 安装和认证

Python 3.11+。运行 `python -m venv .venv` 后，在该环境中运行 `python -m pip install -r requirements.txt`。在面板创建具有目标命令权限的访问密钥，将 `access_key:secret_key` 保存为仅当前用户可读的文件。通过 `HESTIA_BASE_URL` 配置实际 HTTPS 面板地址，`HESTIA_KEY_FILE` 提供密钥文件，`HESTIA_USER` 可作为查询的默认用户名。面板需要允许执行器来源地址。站点创建后会按域名回读。[HestiaCP REST API](https://hestiacp.com/docs/server-administration/rest-api)

使用 `python client_config.py cursor`、`python client_config.py dsh` 或 `python client_config.py codex` 输出对应客户端的配置。将其合并到已有 MCP 或 DSH 插件列表。配置生成器接受重复的 `--env NAME=VALUE` 以传递路径和站点设置。

## 账号管理窗口

账号版从本插件详情页点「管理」→「已连接的账户」→「连接另一个账户」。已连接账号右侧菜单提供重命名、重新连接和断开连接。

使用独立 stdio 客户端时可运行 `python account_manager.py` 设置本机账号。站点与凭据保存在部署端；图形窗口需要 Python 的 Tk 组件。

面板支持创建站点、查询文档根目录、添加域名别名、DNS 查询、FTP 创建与改密、数据库创建/详情/改密/删除。FTP 创建传不含面板用户前缀的短名，改密传实际完整 FTP 用户名。FTP/数据库新密码由本机 HESTIA_PASSWORD_DIR/<reference>.txt 提供。业务表工具按允许的表、字段和主键增删查改。删库、删行先预览，请求发出后由人打开账号管理窗口的「审核删除」审批，再用同一请求执行；十分钟过期、一次有效。

## 多账号和终端更新

MCP 入口为 `router.py`，需要 Python 3.11+。主机在本地保存账号配置，默认位置为 `~/.config/ldai-mcp/hestiacp/accounts.json`，也可用 `LDAI_ACCOUNTS_FILE` 指定。复制 [两账号示例](examples/accounts.example.json)，将地址与路径换成自己的值。每个账号分别设置 HestiaCP 面板地址、访问密钥文件和默认用户。

`ldai_accounts` 仅列出别名和连接状态。配置两个账号后，工具以 `work__` 和 `personal__` 前缀区分，所选工具始终进入该账号的独立子进程。已有单账号配置继续使用原工具名。运行 `python profile_exec.py work -- <程序> <参数…>` 可在同一账号环境完成登录或初始化。完成配置后重新连接 MCP。需要自有适配器时，管理员可为某个账号填写可信 stdio 程序的 `command`、`args` 和 `env`；连接器仅发布当前产品前缀下的业务工具。

安装本仓库后，其他终端可运行 `git pull --ff-only`；Python 服务在其虚拟环境执行 `python -m pip install -r requirements.txt`，随后重新加载客户端。需要固定版本时可检出发布标签。

维护者在 main 提交改进、运行测试，并同步更新 connector.json、两个插件清单的版本，再执行 `python build_plugin.py --push`。此命令将 main 与版本标签一起推送到本仓库，再从已提交文件生成 ZIP。更新既有账号插件时传 `--account-name <既有包名>`，把生成的 ZIP 发布到同一插件。包内 release-source.json 记录精确提交，可与各终端核对。Git 推送与账号插件发布是两个独立步骤。

许可为 **AGPL-3.0-only**。[许可全文](LICENSE)

## 实现参考

按 HestiaCP 原生命令实现网站查询与创建，并对照社区连接器的命令白名单。GitHub 统计核对日期为 2026-11-11。

- [hestiacp/hestiacp](https://github.com/hestiacp/hestiacp) · 4569 stars，默认分支 13253 次提交
- [solkiewicz-artforin/hestiacp-mcp](https://github.com/solkiewicz-artforin/hestiacp-mcp) · 1 stars，默认分支 9 次提交

## 业务表连接

通过 HESTIA_DATA_CONFIG_FILE 指向仅本机可读的 JSON。每个账号提供 database、engine，以及 tables 字典。表条目标明 table、primary_key 和允许的 columns。PostgreSQL 使用 pgsql 并安装 psycopg[binary]；MySQL 使用 mysql 并安装 PyMySQL。两者均需 host、user、password_file 和 TLS ca_file；SQLite 使用已存在的数据库文件。使用独立的最小权限数据库用户。[示例](examples/table-access.example.json)

[原生插件页多账号接入候选版：部署、覆盖范围与验收](native_account/README.md)

使用 Codex 插件页连接、重连和管理多个工作站账号，见[工作站接入](native_account/WORKSTATION.md)。
