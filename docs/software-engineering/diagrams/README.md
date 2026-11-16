# 招聘与求职辅助系统工程图表目录

本目录收录 22 张工程图，每张图提供 PNG、SVG 和可编辑图源，供课程报告和答辩使用。图表依据代码基线 e92e561 整理，使用前请结合目前的系统版本核对。

## 图表目录

**SVG** 适合放大、打印和插入支持矢量图的 Word/PPT；**PNG** 适合直接粘贴；**图源** 用于修改和重新生成。每张图内部都有编号与名称。不要只贴图片：报告中应保留图名，并用一段话解释它解决的问题。

| 编号 | 图名与类型 | 主要用途 | 范围 | SVG / PNG / 图源 |
|---|---|---|---|---|
| F01 | 系统分层架构图 | 解释前端、业务、AI、数据与外部服务 | 当前实现 | [SVG](svg/F01-system-architecture.svg) · [PNG](png/F01-system-architecture.png) · [图源](src/F01-system-architecture.puml) |
| F02 | 系统功能结构图 | 展示 M01–M08 模块与子功能 | 当前实现 | [SVG](svg/F02-functional-structure.svg) · [PNG](png/F02-functional-structure.png) · [图源](src/F02-functional-structure.puml) |
| F03 | 软件包依赖图 | 说明源码目录与依赖方向 | 当前实现 | [SVG](svg/F03-package-dependencies.svg) · [PNG](png/F03-package-dependencies.png) · [图源](src/F03-package-dependencies.puml) |
| F04 | 顶层 DFD | 明确系统与外部实体的数据边界 | 需求分析视图 | [SVG](svg/F04-dfd-context.svg) · [PNG](png/F04-dfd-context.png) · [图源](src/F04-dfd-context.dot) |
| F05 | 一层 DFD | 分解业务处理与数据存储 | 需求分析视图 | [SVG](svg/F05-dfd-level1.svg) · [PNG](png/F05-dfd-level1.png) · [图源](src/F05-dfd-level1.dot) |
| F06 | 二层 DFD | 细化 P4 匹配与报告处理 | 需求分析视图 | [SVG](svg/F06-dfd-match-level2.svg) · [PNG](png/F06-dfd-match-level2.png) · [图源](src/F06-dfd-match-level2.dot) |
| F07 | HR UML 用例图 | 说明招聘人员的使用目标 | 当前实现 | [SVG](svg/F07-hr-use-cases.svg) · [PNG](png/F07-hr-use-cases.png) · [图源](src/F07-hr-use-cases.puml) |
| F08 | 求职者 UML 用例图 | 说明个人匹配、收藏与求职准备 | 当前实现 | [SVG](svg/F08-seeker-use-cases.svg) · [PNG](png/F08-seeker-use-cases.png) · [图源](src/F08-seeker-use-cases.puml) |
| F09 | 核心领域 UML 类图 | 展示实体对象和多重关系 | 当前模型 | [SVG](svg/F09-domain-class.svg) · [PNG](png/F09-domain-class.png) · [图源](src/F09-domain-class.puml) |
| F10 | 数据库 ER 图 | 展示 11 张表及主外键关系 | 当前模型 | [SVG](svg/F10-database-er.svg) · [PNG](png/F10-database-er.png) · [图源](src/F10-database-er.dot) |
| F11 | HR 匹配 UML 顺序图 | 说明批量请求中的单份分析子流程 | 当前实现 | [SVG](svg/F11-hr-match-sequence.svg) · [PNG](png/F11-hr-match-sequence.png) · [图源](src/F11-hr-match-sequence.puml) |
| F12 | 求职匹配 UML 顺序图 | 说明个人报告创建、保存和查询 | 当前实现 | [SVG](svg/F12-seeker-match-sequence.svg) · [PNG](png/F12-seeker-match-sequence.png) · [图源](src/F12-seeker-match-sequence.puml) |
| F13 | 照片解析 UML 顺序图 | 解释本地 OCR 与远端文字分析的分工 | 当前实现 | [SVG](svg/F13-photo-upload-sequence.svg) · [PNG](png/F13-photo-upload-sequence.png) · [图源](src/F13-photo-upload-sequence.puml) |
| F14 | 匹配报告 UML 状态图 | 说明 PENDING、COMPLETED、FAILED | 当前实现 | [SVG](svg/F14-match-state.svg) · [PNG](png/F14-match-state.png) · [图源](src/F14-match-state.puml) |
| F15 | 求职记录 UML 状态图 | 说明可自由切换的手动进度 | 当前实现 | [SVG](svg/F15-saved-job-state.svg) · [PNG](png/F15-saved-job-state.png) · [图源](src/F15-saved-job-state.puml) |
| F16 | 照片解析 UML 活动图 | 说明文件校验、识字与失败处理 | 当前实现 | [SVG](svg/F16-photo-activity.svg) · [PNG](png/F16-photo-activity.png) · [图源](src/F16-photo-activity.puml) |
| F17 | 本地运行 UML 部署图 | 说明端口、进程、文件与外部网络 | 已验证的本地方式 | [SVG](svg/F17-local-deployment.svg) · [PNG](png/F17-local-deployment.png) · [图源](src/F17-local-deployment.puml) |
| F18 | Docker UML 部署图 | 说明 Compose 容器与卷 | 配置方案，未做容器验收 | [SVG](svg/F18-docker-deployment.svg) · [PNG](png/F18-docker-deployment.png) · [图源](src/F18-docker-deployment.puml) |
| F19 | AI 流水线活动图 | 解释 5 个 Agent 类与 4 步执行 | 当前实现 | [SVG](svg/F19-ai-pipeline.svg) · [PNG](png/F19-ai-pipeline.png) · [图源](src/F19-ai-pipeline.puml) |
| F20 | Git 配置管理流程图 | 展示验证、排密钥、提交与推送过程 | 工作流程说明，非 CI 平台 | [SVG](svg/F20-configuration-workflow.svg) · [PNG](png/F20-configuration-workflow.png) · [图源](src/F20-configuration-workflow.dot) |
| F21 | 相对周甘特图 | 建议后续课程材料完善排期 | 建议计划，非实际工期 | [SVG](svg/F21-relative-gantt.svg) · [PNG](png/F21-relative-gantt.png) · [图源](src/F21-relative-gantt.dot) |
| F22 | UI 页面导航图 | 说明两种角色的页面入口 | 当前实现 | [SVG](svg/F22-ui-navigation.svg) · [PNG](png/F22-ui-navigation.png) · [图源](src/F22-ui-navigation.dot) |

