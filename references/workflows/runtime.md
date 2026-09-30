# 运行入口与降级

先使用现有解释器，不为检索安装软件或改变执行策略。PowerShell 在 Skill 根目录运行 `./scripts/run.ps1 search_law.py --law 民法典 --article 577`；入口依次检查 CHINALAW_PYTHON、PATH 和宿主已有运行时，要求 Python 3.12+，并启用 UTF-8。其他系统用已有 `python3 -B -X utf8 scripts/search_law.py ...`。文档中 `python scripts/...` 是通用示意，可替换为该入口与同名脚本。

若执行策略或权限阻止入口，不修改系统设置；可通过宿主提供的依赖查询定位已有解释器，用其绝对路径运行 Python 脚本。解释器路径只留本机，不写入通用文件。仍不可用时，用只读文本检索定位法律原文及条号，明确脚本未运行；不能把替代检索说成工具测试通过。

测试用 `python -B -X utf8 -m unittest discover -s tests -v`。将临时目录和测试输出设在 Skill 之外的私人位置；不得把原始测试答复、运行日志或快照加入发布清单。
