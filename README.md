# 一个放飞梦想的网页开发集

## say

`say` 是一个把一句话拆成临时文件夹名的小工具，适合配合 VS Code 左侧文件目录观看文字逐个出现再逐个消失。

直接运行：

```bash
python -m say --dir /tmp/say-demo how about today?
```

安装成命令后运行：

```bash
python -m pip install -e .
say --dir /tmp/say-demo how about today?
```

这条命令会把文本拆成 `how`、`about`、`today`、`?`，并依次创建：

```text
a-how
b-about
c-today
d-?
```

默认每隔 `0.75` 秒出现一个文件夹，全部出现后停留 `3` 秒，再按同样间隔依次删除。可以用 `--interval` 和 `--hold` 调整：

```bash
say --dir /tmp/say-demo --interval 0.75 --hold 3 how about today?
```

Linux 上 `?` 可以直接作为文件夹名。Windows 不允许 `?`、`*`、`:` 等字符出现在文件夹名里，工具会自动换成视觉接近的全角字符，例如 `?` 会显示成 `？`。

远程运行：

```bash
say -r cys --dir /tmp/say-demo hello?
say -r xb --dir /tmp/say-stage how about today?
```

内置远程别名：

```text
cys -> root@180.163.219.95:22804
xb  -> root@180.163.219.95:22806
```

远程模式不会要求服务器预先安装这个工具；本机会通过 SSH 把一段临时 Python 脚本发到远端执行。远端需要能登录 SSH，并且有 `python3`。如果省略 `--dir`，文件夹会出现在远端命令的当前目录，通常是 `/root`。

默认远程流程不用 `scp`。它会先通过 SSH 执行 `cat > /tmp/say_remote_worker_<random>.py`，把简化 worker 写到远端，再通过 `ssh` 运行它。`<random>` 每次运行都会变化，避免覆盖远端已有文件。运行前先确认本机能免密登录目标机器：

```bash
ssh -p 22806 root@180.163.219.95
```

如果看到 `Permission denied (publickey,password)`，说明 SSH key、密码登录或服务器授权还没配好，`say -r xb ...` 也会失败。

排查远程效果时，可以把停留时间调长，并打开事件输出：

```bash
say -r xb --dir /tmp/say_stage --hold 30 --verbose how about today?
```

远程上传和执行都有 timeout。上传默认 15 秒，执行 timeout 会按动画时长自动加上这 15 秒余量。可以手动调整：

```bash
say -r xb --dir /tmp/say_stage --remote-timeout 30 --hold 30 --verbose how about today?
```

如果想尝试其他传输方式，也可以显式指定：

```bash
say -r xb --remote-transfer scp --dir /tmp/say_stage how about today?
say -r xb --remote-transfer stdin --dir /tmp/say_stage how about today?
```
