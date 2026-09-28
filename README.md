# chinalaw-waylon-expert

面向 Codex 等本地 Skill 运行环境的中国法律检索与案件分析工具。它把法律原文、程序期限、证据矩阵、双方论证和版本核验放进同一工作流，并明确材料不足时的结论边界。

## 按需加载与检索性能

`SKILL.md` 只保留任务分流和共同核验要求；法域细节、全案方法与维护清单按任务读取。查条文可直接运行检索脚本，无需把整份目录或统一索引读入对话。

检索自动复用本地 SQLite 缓存，使用内容指纹检测资料变化；命中条文仍从 Markdown 原文读取。缓存首次构建有额外成本，后续查询复用；不可用时自动回退原始检索。缓存不提交、不打包，也不代表已经核验法律当前效力。

```text
python scripts/search_law.py --law 民法典 --article 577
python scripts/search_law.py --law 市场监管处罚程序 --article 18
python scripts/search_law.py --keyword 电子送达 --limit 5
python scripts/search_law.py --law 民法典 --article 577 --no-cache
python scripts/benchmark_search.py --runs 7
```

缓存失效、短关键词兼容性及测量边界见 [检索性能与维护](references/workflows/search-performance.md)。

## 当前知识库

| 文件类型 | 文件数量 | 索引记录 |
|---|---:|---:|
| 法律 | 23 | 4,493 |
| 司法解释 | 48 | 1,893 |
| 行政法规 | 1 | 55 |
| 部门规章 | 3 | 198 |
| **合计** | **75** | **6,639** |

《市场监督管理行政处罚程序规定》按2022年第二次修正文本收录87条。《刑法》的505条索引记录包含“之一”等增补条款，因此多于452个基础条号。版本、效力说明、别名和文件路径见 `references/law-catalog.json`。

## 分析与案件整理

按请求、抗辩、事实、证据、法律要件、程序期限和救济组织分析，区分本地资料快照与在线核验结果。公司治理、合同履行、印章授权、担保融资、保全执行、破产及商事仲裁等问题可按需加载相应模块。

公开案例学习卡用于比较决定性事实和适用边界，不是完整案卷或亲历办案记录。案件工作台由用户在私人目录建立；关联案件分别保存资料，并按证据来源和程序相互影响进行统筹。

使用 `scripts/new_matter.py` 创建案件工作台，商事事项可加 `--profile commercial`。`scripts/audit_matter.py` 检查资料准备缺口，不计算胜诉率。

## 一句话安装

在 Codex 中输入：

```text
请使用 skill-installer 从 GitHub 仓库 https://github.com/xiezhicong3288-wq/chinalaw-waylon-expert 安装这个 Skill。
```

也可以下载 ZIP 或克隆仓库后安装完整目录。必须保留 `SKILL.md`、`references/`、`scripts/` 的相对位置。

### ZIP 中文路径兼容

发布ZIP必须使用仓库内的打包器：

```text
python scripts/package_skill.py
```

打包器会同时写入UTF-8文件名标志、Unix主机标识和Info-ZIP Unicode Path冗余字段，并在生成后逐项比较源码与归档路径，避免部分解压器把中文文件名误按DOS代码页处理。

## 使用示例

```text
请使用 chinalaw-waylon-expert 查询民事诉讼法第127条，引用原文并说明适用前提。
请分析这份股权争议：建立请求权、抗辩、要件、证据、期限和执行风险矩阵。
行政处罚决定已经送达，请列出申请复议和起诉需要确认的起算事实，缺信息时不要猜截止日期。
请比较公司法新旧规则，但先确认行为发生时间和应适用的版本。
请从控辩双方分别分析该刑事案件；未经证据支持，不得断言构成犯罪。
```

建立本地案件工作台：

```text
python scripts/new_matter.py --output C:\path\to\private-matter --title 示例案件
python scripts/new_matter.py --profile commercial --output C:\path\to\commercial-matter --title 商事案件
python scripts/audit_matter.py --input C:\path\to\private-matter\matter.json
```

脚本默认拒绝在 Git 仓库内创建工作台；只有明确确认仓库权限和材料脱敏后，才使用 `--allow-git-repo`。

## 验证

```text
python scripts/validate_knowledge_base.py
python scripts/audit_sources.py
python -m unittest discover -s tests -v
python scripts/package_skill.py
```

`audit_sources.py --online` 会检查来源网址可达性。自动测试验证数据结构和检索行为，不等于律师审阅或个案法律意见。

历史测试记录见 [商事验证记录](evals/reports/2026-09-25-phase5.md)和[通用验证记录](evals/reports/2026-09-25-phase4.md)。记录只适用于当时的版本和已测样本。

## 文件结构

- `SKILL.md`：路由、强制工作方法、回答结构与边界。
- `references/law-catalog.json`：权威文件目录和版本。
- `references/law-index.json`：统一条文索引。
- `references/source-manifest.json`：来源、下载日期和原始文件哈希。
- `references/民法典/`、`references/法律法规/`、`references/行政法规/`、`references/部门规章/`、`references/司法解释/`：结构化原文。
- `references/workflows/`：案件、证据、期限、版本、案例和改进流程。
- `references/常用法律文书/`：法律分析备忘录、证据目录和案件时间线模板。
- `references/cases/`：13个最高人民法院指导案例学习卡，非完整案卷。
- `references/experience/`：案件原型、常见失败模式和经验迁移方法。
- `references/practice/`：案件体检、证据工程、庭审、和解执行、上诉复盘和高风险案件工作流。
- `references/commercial/`：商事专项工作流和12类常见决策模式。
- `scripts/`：法律与案例检索、校验、来源审计、案件工作台和准备缺口审计工具。
- `scripts/package_skill.py`：生成并验证兼容中文路径的安装ZIP。
- `tests/` 与 `evals/`：回归测试和行为评估材料。

## 数据与边界

资料快照整理于 **2026年9月24日至28日**，不会自动更新。实际案件需要再次核验最新法律、司法解释、案例、行政法规、部门规章、地方规则及受理机关实践。联网检索不应发送未脱敏案卷；请勿在公开 Issue 中提交身份证号、联系方式、合同秘密或案件材料。

## 授权说明

仓库公开可见，但未指定开源许可证，因此不属于获得开源许可授权的软件。除适用法律或平台规则另有规定外，复制、修改、再分发或商业使用前请联系仓库作者取得许可。
