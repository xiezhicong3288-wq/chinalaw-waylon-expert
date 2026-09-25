# 2026-09-25 ZIP中文路径兼容性修复

## 问题

旧发布ZIP中的中文路径具有UTF-8标志，但条目主机类型仍为DOS。WorkBuddy安装时按CP866解释文件名，导致`references/法律法规/`等路径乱码，`law-catalog.json`引用失效。

## 修复

- 新增仓库内 `scripts/package_skill.py`，所有条目统一标记为Unix主机类型。
- 含非ASCII路径的条目同时写入ZIP规范的UTF-8标志和Info-ZIP Unicode Path额外字段。
- 打包后逐项比较源码文件与归档路径，检查重复、遗漏、UTF-8标志、主机类型和Unicode额外字段。
- 在临时目录完整解压并比较文件清单；输出ZIP不得位于待打包Skill目录内。
- 增加回归测试，直接检查《中华人民共和国刑法》路径的三项Unicode元数据。

## 验证

- 新ZIP包含36个非ASCII路径条目，全部具有UTF-8标志、Unix主机标识和Unicode Path额外字段。
- Windows PowerShell `Expand-Archive`全新解压后，`validate_knowledge_base.py`通过。
- 解压目录中检索《刑法》第390条成功。
- 解压目录中检索案例卡GC179成功。
- 全部31项回归测试通过。

该修复解决ZIP路径编码兼容问题，不改变法律资料内容。
