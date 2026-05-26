-- =============================================================================
-- ChatBI 会话持久化表结构
-- 数据库：与 .env 中 MYSQL_DATABASE 一致（如 testDatabase）
-- 连接：MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD
--
-- 表关系：
--   chat_bi_conversations_table (1) ──< chat_bi_messages_table (N)
--   删除会话时，关联消息通过外键 ON DELETE CASCADE 级联删除。
--
-- 说明：
--   - 应用启动时 ensure_tables() 会自动执行本文件，但会跳过 DROP 语句（不丢数据）。
--   - 需要删表重建时，请手动执行本文件全文（含 DROP），或运行：
--       python backend/scripts/rebuild_conversation_tables.py
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 删表（重建时使用；先删子表 messages，再删主表 conversations）
-- ---------------------------------------------------------------------------
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS chat_bi_messages_table;
DROP TABLE IF EXISTS chat_bi_conversations_table;
SET FOREIGN_KEY_CHECKS = 1;


-- ---------------------------------------------------------------------------
-- 表：chat_bi_conversations_table
-- 释义：ChatBI 对话会话主表，一条记录代表用户的一次完整聊天线程（左侧会话列表项）。
--       保存会话元数据（标题、问数模式、表筛选等），具体问答内容存 messages 表。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_bi_conversations_table (
    id          VARCHAR(36)  NOT NULL COMMENT '会话唯一标识，UUID，由前端或 API 生成',
    user_id     VARCHAR(64)  NOT NULL COMMENT '所属用户标识，对应前端 CURRENT_USER.username，用于多用户隔离',
    title       VARCHAR(256) NOT NULL DEFAULT '新对话' COMMENT '会话标题，默认取首条用户问题摘要，可手动修改',
    mode        VARCHAR(16)  NOT NULL DEFAULT 'chatbi' COMMENT '问数模式：chatbi=ChatBI意图路由（查数/分析/对话）；kb=仅知识库RAG问答',
    table_name  VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'ChatBI模式下可选的业务表名筛选，空字符串表示不限制表',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '会话创建时间',
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '会话最后更新时间（新消息写入时自动刷新）',
    PRIMARY KEY (id),
    INDEX idx_user_updated (user_id, updated_at DESC)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='ChatBI对话会话主表：存储聊天线程元数据（标题、模式、用户、表筛选）';


-- ---------------------------------------------------------------------------
-- 表：chat_bi_messages_table
-- 释义：ChatBI 对话消息明细表，一条记录代表会话中的一条 UI 消息（用户提问或助手回复）。
--       同一轮 ask（turn_id）可能有多条 assistant 消息（如查数结果、图表、追问建议）。
--       content 字段为 JSON，结构与前端 ChatMessage 各 kind 的字段对应。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_bi_messages_table (
    id              VARCHAR(36) NOT NULL COMMENT '消息唯一标识，UUID',
    conversation_id VARCHAR(36) NOT NULL COMMENT '所属会话 ID，外键关联 chat_bi_conversations_table.id',
    turn_id         VARCHAR(36) NOT NULL COMMENT '同一轮提问的唯一标识；一次 /api/ask/stream 请求内产生的消息共享同一 turn_id',
    seq             INT         NOT NULL DEFAULT 0 COMMENT '同一 turn 内的消息顺序号，用于还原 UI 展示顺序（0=用户问题，1+=助手回复）',
    role            VARCHAR(16) NOT NULL COMMENT '消息角色：user=用户；assistant=助手',
    kind            VARCHAR(32) NOT NULL COMMENT '消息类型：text/query-result/analysis-report/plot/followup/kb-answer/error 等，对应前端 MessageKind',
    content         JSON        NOT NULL COMMENT '消息内容 JSON，含 text/sql/queryResult/reportMd/figureJson 等，按 kind 存不同字段',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '消息写入时间',
    PRIMARY KEY (id),
    INDEX idx_conv_turn (conversation_id, turn_id, seq),
    INDEX idx_conv_created (conversation_id, created_at),
    CONSTRAINT fk_chat_bi_messages_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES chat_bi_conversations_table (id)
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='ChatBI对话消息明细表：存储每条问答消息及查数/报告/图表等结构化内容';
