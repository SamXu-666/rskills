# rwrite

`rwrite` 是一个面向中文公众号写作的个人风格 skill。

这一版的目标不是做一个“什么都自动化”的内容工厂，而是先把最关键的事情做好：

- 写出来越来越像你
- 能从你过去的文章里学风格
- 能从你后续的改稿里继续学习
- 能记录历史，避免反复写成一个样子

它基于现有写作工具层做轻量改造，保留可复用的组件，同时把核心工作流收敛到“个人写作闭环”。

## 当前定位

`rwrite` 当前优先服务这类场景：

- 你自己长期写公众号
- 你有已经发表过的文章，想导入做风格样本
- 你愿意在初稿基础上做少量改稿，让系统慢慢学会你的表达

它现在不是一个完整的“热点抓取到自动发草稿箱”的重型系统说明文档。  
如果某些旧能力还在仓库里，那代表它们**可能存在基础代码**，不代表它们是这版 `rwrite` 的主工作流。

## 交互模式

`rwrite` 支持两种使用方式：

### 1. 默认模式

默认就是“你给题目，我尽量往前推进”。

适合这些情况：

- 你已经有明确题目
- 你希望它先自己判断框架和策略
- 你更想先看一个成型初稿，再决定怎么改

默认模式下，系统通常会自动完成这些动作：

- 读取你的风格配置
- 命中范文库
- 命中 learned rules
- 参考对标账号库
- 自动选写作框架
- 自动选内容增强策略
- 生成标题候选、摘要、标签

### 2. 交互模式

如果你不想让它一口气往下写，可以直接说：

- `用交互模式`
- `先别急着写，先给我几个框架`
- `先给我标题和结构，我选一个`
- `先给我几个对标方向`

交互模式下，更适合先停在这些节点让你确认：

- 题目是否成立
- 选哪个框架
- 借哪个对标账号的手法
- 标题方向怎么走
- 初稿是否继续扩写

### 最推荐的用法

如果你题目很明确：

- 直接用默认模式

如果你还在犹豫怎么写：

- 先用交互模式，让它先给你：
  - 框架选项
  - 对标账号建议
  - 标题候选
  - brief

## 当前已实现

这版已经对齐的核心能力有：

### 1. 风格配置

用 `style.yaml` 管你的账号级写作设定，至少包括：

- `topics`
- `tone`
- `voice`
- `content_style`
- `author`
- `writing_persona`
- `wechat_theme`
- `blacklist`

示例见 `style.example.yaml`。

### 2. 写作人格

首版采用单人格优先，不做复杂人格系统。

默认新增人格是：

- `personas/friend-voice.yaml`

它偏朋友式口语，重点控制：

- 句长倾向
- 第一人称密度
- 口语化程度
- 情绪强度
- 结尾习惯
- 常见表达替换倾向

### 3. 范文库

支持把你已发表的本地 Markdown 批量导入到范文库中。

导入后会进入：

- `references/exemplars/index.yaml`
- `references/exemplars/*.md`

每篇文章会尽量提取这些片段：

- 开头
- 转折
- 情绪高点
- 结尾

### 4. 学习改稿

支持本地 Markdown diff 学习。

也就是：

1. 系统先给你初稿
2. 你手动修改本地 Markdown
3. 系统比较 `draft -> final`
4. 把稳定偏好沉淀到 `learned_rules.yaml`

当前重点学习的是这些规则：

- 更偏好的用词
- 更口语还是更克制
- 第一人称增减
- 段落长短倾向
- 开头偏好
- 结尾偏好
- 少总结腔

### 5. 历史记录

会把每篇文章的关键信息写入 `history.yaml`，用于：

- 避免近期重复主题
- 避免连续重复同一框架
- 记录 persona / 框架 / 策略 / 范文命中 / learned rules 命中
- 给后续传播效果复盘预留字段

### 6. 写作框架选择

当前内置的是轻量框架，而不是旧版那套更重的完整流水线规则。

现在保留 5 类：

- 清单型
- 观点型
- 故事型
- 复盘型
- 教程型

定义见 `references/personal_frameworks.yaml`。

### 7. 内容增强策略

当前只保留 3 个最核心的增强方向：

- 信息密度增强
- 细节具体化
- 观点锐化

定义见 `references/personal_enhance.yaml`。

### 8. 质量校验

支持轻量质检，主要检查：

- 标题是否太平
- 开头是否缺少钩子
- 是否命中禁用词
- 是否缺少具体细节
- 段落节奏是否太平均
- 标签关键词是否完全没进正文

### 9. 微信排版兼容（弱实现）

这版保留的是“够用”的微信排版能力，不强调复杂主题学习。

当前可直接使用：

- Markdown 转 HTML 预览
- 基础公众号友好排版
- 主题选择与画廊预览

CLI 入口仍在 `toolkit/cli.py`。

### 10. SEO 分析（弱实现）

当前不是复杂 SEO 系统，而是轻量辅助：

- 3 个标题候选
- 1 个摘要
- 5 个标签
- 关键词覆盖提示

## 当前不作为主能力承诺

下面这些内容如果仓库里还有旧代码，不代表它们是这版 `rwrite` 的正式主链路：

- 热点抓取驱动的完整自动选题系统
- 从搜索到素材采集的全自动重型写作链路
- 主题学习
- 完整配图自动化
- 自动推送公众号草稿箱
- 完整传播数据回填与复盘闭环

后续可以继续做，但不应该写成“这版已经完整交付”。

## 快速开始

### 1. 配置风格

先复制配置模板：

```bash
cp style.example.yaml style.yaml
```

然后填成你自己的内容方向和语气。

### 2. 导入旧文建立范文库

```bash
python3 toolkit/cli.py writer-import path/to/your-markdown-folder
```

### 3. 生成写作 brief

```bash
python3 toolkit/cli.py writer-plan "AI 工具到底怎么选" --keyword ChatGPT --keyword 新手
```

它会输出：

- 选中的写作框架
- 增强策略
- 命中的范文
- 当前 learned rules
- 标题候选 / 摘要 / 标签

### 4. 学习你的改稿

```bash
python3 toolkit/cli.py writer-learn --draft draft.md --final final.md
```

### 5. 自检

```bash
python3 toolkit/cli.py writer-qc article.md
```

### 6. 写入历史

```bash
python3 toolkit/cli.py writer-log article.md --topic "AI 工具到底怎么选"
```

## CLI 命令

这版和个人写作闭环直接相关的命令是：

```bash
python3 toolkit/cli.py writer-import path/to/folder
python3 toolkit/cli.py writer-plan "你的选题"
python3 toolkit/cli.py writer-learn --draft draft.md --final final.md
python3 toolkit/cli.py writer-qc article.md
python3 toolkit/cli.py writer-log article.md --topic "你的选题"
```

另外仍可继续使用的工具层命令有：

```bash
python3 toolkit/cli.py preview article.md
python3 toolkit/cli.py themes
python3 toolkit/cli.py gallery
python3 toolkit/cli.py publish article.md
```

但要注意，`publish` 属于旧工具层能力，不代表当前 README 主推的是“全自动发布链路”。

## 目录说明

当前和 `rwrite` 这版最相关的目录/文件有：

- `SKILL.md`
- `style.example.yaml`
- `scripts/personal_writer.py`
- `personas/friend-voice.yaml`
- `references/personal_frameworks.yaml`
- `references/personal_enhance.yaml`
- `toolkit/cli.py`

运行过程中会逐步产生这些用户数据：

- `style.yaml`
- `history.yaml`
- `learned_rules.yaml`
- `references/exemplars/index.yaml`
- `references/exemplars/*.md`

## 现在最适合怎么用

如果你现在就想把 `rwrite` 用起来，最推荐的顺序是：

1. 先配好 `style.yaml`
2. 导入你过去 3-10 篇最能代表你的文章
3. 先用 `writer-plan` 看系统怎么理解你的题目
4. 生成初稿后亲自改一轮
5. 用 `writer-learn` 让它开始学你
6. 用 `writer-qc` 和 `writer-log` 把闭环补上

这样它不会一开始就像“万能自动化系统”，但会比较稳地朝“越来越像你”这个方向走。
