# chinalaw-waylon-expert

面向 Codex 等本地 Skill 运行环境的中国法律检索与案件分析工具。它把法律原文、程序期限、证据矩阵、双方论证和版本核验放进同一工作流，并明确材料不足时的结论边界。

## 按需加载与检索性能

`SKILL.md` 只保留任务分流和共同核验要求；法域细节、全案方法与维护清单按任务读取。查条文可直接运行检索脚本，无需把整份目录或统一索引读入对话。

检索自动复用本地 SQLite 缓存，使用内容指纹检测资料变化；命中条文仍从 Markdown 原文读取。缓存首次构建有额外成本，后续查询复用；不可用时自动回退原始检索。缓存不提交、不打包，也不代表已经核验法律当前效力。

```text
python scripts/search_law.py --law 民法典 --article 577
python scripts/search_law.py --keyword 电子送达 --limit 5
python scripts/search_law.py --law 民法典 --article 577 --no-cache
python scripts/benchmark_search.py --runs 7
```

缓存失效、短关键词兼容性及测量边界见 [检索性能与维护](references/workflows/search-performance.md)。

## 当前知识库

| 类别 | 权威文件 | 索引记录 |
|---|---|---:|
| 基础民事 | 《中华人民共和国民法典》 | 1,260 |
| 宪法、刑事实体与程序 | 《中华人民共和国宪法》《中华人民共和国刑法》《中华人民共和国刑事诉讼法》 | 956 |
| 民事程序与证据 | 《中华人民共和国民事诉讼法》《最高人民法院关于民事诉讼证据的若干规定》 | 405 |
| 行政 | 《中华人民共和国行政处罚法》《中华人民共和国行政复议法》《中华人民共和国行政诉讼法》 | 279 |
| 公司、市场与消费者 | 《中华人民共和国公司法》《中华人民共和国反垄断法》《中华人民共和国反不正当竞争法》《中华人民共和国消费者权益保护法》 | 440 |
| 劳动与社会保障 | 《中华人民共和国劳动法》《中华人民共和国劳动合同法》《中华人民共和国社会保险法》 | 303 |
| 仲裁 | 《中华人民共和国仲裁法》 | 96 |
| **合计** | **16部法律、1部司法解释** | **3,739** |

《刑法》的505条索引记录包含“之一”等增补条款，因此多于452个基础条号。版本、效力说明、别名和文件路径见 `references/law-catalog.json`。

## 本次升级

- 补入民事诉讼法、刑事诉讼法、行政复议法、公司法、劳动合同法、2025年修订仲裁法，以及民事诉讼证据规定。
- 新增法域路由、请求与抗辩拆解、证据矩阵、双方最强论点复核、程序期限核验和分层结论规则。
- 新增 `scripts/new_matter.py`，可在用户私有目录建立 `matter.md` 与 `matter.json` 案件工作台。
- 新增 `scripts/audit_sources.py`，检查官方来源域名、哈希、下载日期和可选在线可达性。
- 保留明确边界：不会虚构执业资格、数十年亲历经验、案例或确定结果；升级流程也不会脱离用户授权自行运行。

## 案例经验升级

案例库现有 **12个最高人民法院指导案例学习卡**，覆盖关联公司、合同执行、代位权、抵押、银行卡盗刷、劳动关系、违法解除、竞业限制、行政许可、行政赔偿、交通肇事无罪和技术秘密。每张新增案例卡均整理决定性事实、证据结构、双方论点、程序节点及不适用边界。

`references/experience/` 另含10类案件原型和18类常见失败模式。这里的经验来自公开案例归纳，不冒充亲历办案经验。

## 办案能力升级

第四阶段增加完整的案件体检和诉讼准备闭环：从救济目标反推请求及要件，建立证据来源、完整性与矛盾台账，预演对方最强阻断点，并分别处理庭审、和解、保全执行、裁判复盘及民刑行交叉风险。

`scripts/new_matter.py` 现在生成第二版结构化案件工作台；`scripts/audit_matter.py` 可以发现尚未填写的事实、证据、期限、争点、风险和行动项。审计只检查准备完整性，不计算胜诉率。

## 商事案件专项升级

商事模块新增8份专项工作流和12类决策模式，覆盖合同链与履行、公司股权、授权印章、担保融资、价款与损失、保全执行、困境企业、商事仲裁和涉外交易。它要求分别建立交易结构、合同文件、履行、资金、授权、担保顺位和资产回收台账。

商事工作台使用 `--profile commercial` 创建，并由同一个审计工具检查11个商事模块是否已经评估。

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

当前数据、工具和独立前向测试见 [第五阶段商事能力验证记录](evals/reports/2026-09-25-phase5.md)；[第四阶段记录](evals/reports/2026-09-25-phase4.md)保留为通用办案能力基线。

## 文件结构

- `SKILL.md`：路由、强制工作方法、回答结构与边界。
- `references/law-catalog.json`：权威文件目录和版本。
- `references/law-index.json`：统一条文索引。
- `references/source-manifest.json`：来源、下载日期和原始文件哈希。
- `references/民法典/`、`references/法律法规/`、`references/司法解释/`：结构化原文。
- `references/workflows/`：案件、证据、期限、版本、案例和改进流程。
- `references/常用法律文书/`：法律分析备忘录、证据目录和案件时间线模板。
- `references/cases/`：12个最高人民法院指导案例学习卡，非完整案卷。
- `references/experience/`：案件原型、常见失败模式和经验迁移方法。
- `references/practice/`：案件体检、证据工程、庭审、和解执行、上诉复盘和高风险案件工作流。
- `references/commercial/`：商事专项工作流和12类常见决策模式。
- `scripts/`：法律与案例检索、校验、来源审计、案件工作台和准备缺口审计工具。
- `scripts/package_skill.py`：生成并验证兼容中文路径的安装ZIP。
- `tests/` 与 `evals/`：回归测试和行为评估材料。

## 数据与边界

资料快照整理于 **2026年9月24日至25日**，不会自动更新。实际案件需要再次核验最新法律、司法解释、案例、行政法规、部门规章、地方规则及受理机关实践。联网检索不应发送未脱敏案卷；请勿在公开 Issue 中提交身份证号、联系方式、合同秘密或案件材料。

## 授权说明

仓库公开可见，但未指定开源许可证，因此不属于获得开源许可授权的软件。除适用法律或平台规则另有规定外，复制、修改、再分发或商业使用前请联系仓库作者取得许可。
