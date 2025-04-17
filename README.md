# Zepy

下载 Twitter 点赞媒体文件、通过 Telegram 消息链接下载媒体、转发媒体消息给 Telegram Bot 下载。

## ✨ 功能一览

- 下载 Twitter 点赞的媒体内容
- 通过 Telegram bot 下载媒体文件
- 支持解析 Telegram 消息链接进行下载

## 🚀 快速开始

1. 获取项目

```shell
git clone https://github.com/huk10/zepy
cd zepy
```

2. 安装 Pixi

   确保已经安装了 Pixi。如果没有安装，请参考 [Pixi 官方文档](https://pixi.sh/latest) 进行安装。

3. 安装依赖

```shell
pixi install
```

4. 配置参数

   创建一个 `configure.yaml` 文件，并参考下方配置示例填写。

## 🔧 使用方式

### 命令定义（`pyproject.toml`）

```toml
[tool.pixi.tasks]
bot = "python -m app.bin.start_telegram_bot"
twitter = "python -m app.bin.download_twitter_media"
telegram = "python -m app.bin.download_telegram_media"
```

### 启动命令

```shell
pixi run bot        # 启动 Telegram bot 服务
pixi run twitter    # 下载 Twitter 媒体
pixi run telegram   # 下载 Telegram 链接媒体
```

## 📘 使用指南

### 下载 Twitter 点赞媒体

1. 配置 Twitter 信息（见配置说明）。
2. 运行 `pixi run twitter` 命令。
3. 媒体将保存至配置中指定目录。

### 下载 Telegram 消息链接媒体

1. 在配置中指定 Telegram 信息及链接路径。
2. 在 `urls_path` 文件中添加链接（每行一个）。
3. 运行 `pixi run telegram` 自动下载。

✅ 支持链接格式：

```markdown
- 普通频道/群组消息：
  - https://t.me/c/<channel>/<message>
  - https://t.me/<username>/<message>
- 评论消息
  - https://t.me/c/<channel>/<message>?comment=<comment>
  - https://t.me/<username>/<message>?comment=<comment>
- 主题消息
  - https://t.me/<username>/<message>?thread=<thread>
  - https://t.me/c/<channel>/<message>?thread=<thread>
  - https://t.me/<username>/<thread>/<message>
  - https://t.me/c/<channel>/<thread>/<message>
```

下面是官方文档中的一些链接格式说明：

- https://core.telegram.org/api/links#message-links
- https://core.telegram.org/api/bots/ids

#### 启动 Telegram bot

1. 配置 Telegram Bot 信息。
2. 运行 `pixi run bot` 命令。

说明：

- 启动时需验证 User 身份（输入手机验证码）。
- Bot 支持接收用户转发的媒体和消息链接并自动下载。
- 由于 Telegram 链接仅指向单条媒体，bot 不支持一次性下载整个相册。

## 🗂️ 输出文件说明

| 文件/目录                  | 描述                           |
| -------------------------- | ------------------------------ |
| `./caches.txt`             | 已下载媒体缓存，避免重复下载   |
| `./logs`                   | 日志文件目录                   |
| `./outputs`                | 程序其他输出文件目录（可忽略） |
| `./bot-session.session`    | Bot 会话信息，勿手动删除       |
| `./client-session.session` | User 会话信息，勿手动删除      |

## ⚙️ 配置文件说明（configure.yaml）

### 通用配置

```yaml
max_concurrent: 5 # 最大并发数（1-12）
cache_disabled: false # 是否禁用缓存
cache_file: ./caches.txt # 缓存路径
storage_directory: ./downloads # 文件保存目录
proxy: socks5://127.0.0.1:7890 # Telegram 代理（可选）
```

### Twitter 配置

```yaml
twitter:
  # cookie 中的字段
  ct0: xxxxx
  # cookie 中的字段
  auth_token: xxxxx
  # 用户名称（@ 后面的字符）
  screen_name: xxxxx
  # 只下载图片-默认 false
  only_image: false
  # 只下载视频-默认 false
  only_video: false
```

### Telegram 配置

如果不需要运行 bot 是不需要 bot_token 的，但是还没有精力分开这些配置，后面考虑分开。

```yaml
telegram:
  # Telegram 手机号-国际码+手机号
  phone: +86xxxxx
  # Telegram API ID
  api_id: 一个整数数字
  # Telegram API Hash
  api_hash: xxxxxx
  # Telegram Bot Token
  bot_token: xxxxx
  # 存储 Telegram 链接的文件路径
  urls_path: ./links.txt
```

## 🧪 完整配置示例

```yaml
max_concurrent: 5
cache_disabled: false
cache_file: ./caches.txt
storage_directory: ./downloads
proxy: socks5://127.0.0.1:7890

twitter:
  # cookie 中的字段
  ct0: xxxxx
  # cookie 中的字段
  auth_token: xxxxxx
  # 用户名称（@ 后面的字符）
  screen_name: xxxx
  # 只下载图片
  only_image: false
  # 只下载视频
  only_video: false

telegram:
  phone: +861111111111
  # Telegram API ID
  api_id: 10000000
  # Telegram API Hash
  api_hash: xxxxxxx
  # Telegram Bot Token
  bot_token: xxxxxxx
  # 存储 Telegram 链接的文件路径
  urls_path: ./links.txt
```

## License
The [MIT License](./LICENSE).
