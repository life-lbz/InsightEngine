-- ========================================
-- 知识库版本表（保持原有，增加审计字段）
-- ========================================
CREATE TABLE IF NOT EXISTS kb_versions (
    course_id VARCHAR(128) NOT NULL,
    kb_version VARCHAR(191) NOT NULL,
    version_seq BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0,
    doc_collection VARCHAR(191) NOT NULL,
    faq_collection VARCHAR(191) NOT NULL,
    question_collection VARCHAR(191) NOT NULL,
    PRIMARY KEY (course_id, kb_version)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 课程表（增加审计字段）
-- ========================================
CREATE TABLE IF NOT EXISTS courses (
    course_id VARCHAR(128) PRIMARY KEY,
    title VARCHAR(191) NOT NULL,
    description TEXT NULL,
    active_kb_version VARCHAR(191) NOT NULL DEFAULT 'kb_manual_v1',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 章节表（增加审计字段）
-- ========================================
CREATE TABLE IF NOT EXISTS chapters (
    chapter_id VARCHAR(191) PRIMARY KEY,
    course_id VARCHAR(128) NOT NULL,
    chapter_no INT NOT NULL DEFAULT 0,
    title VARCHAR(191) NOT NULL,
    summary TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0,
    INDEX idx_chapters_course (course_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 知识点表（增加审计字段）
-- ========================================
CREATE TABLE IF NOT EXISTS knowledge_points (
    point_id VARCHAR(191) PRIMARY KEY,
    course_id VARCHAR(128) NOT NULL,
    chapter_id VARCHAR(191) NOT NULL,
    name VARCHAR(191) NOT NULL,
    summary TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0,
    INDEX idx_points_course_chapter (course_id, chapter_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 题库表（增加审计字段）
-- ========================================
CREATE TABLE IF NOT EXISTS questions (
    question_id VARCHAR(191) PRIMARY KEY,
    course_id VARCHAR(128) NOT NULL,
    chapter_id VARCHAR(191) NULL,
    point_id VARCHAR(191) NULL,
    question_type VARCHAR(32) NOT NULL DEFAULT 'single_choice',
    difficulty VARCHAR(16) NOT NULL DEFAULT 'medium',
    question_text TEXT NOT NULL,
    answer TEXT NULL,
    explanation TEXT NULL,
    source VARCHAR(128) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0,
    INDEX idx_questions_course_point (course_id, point_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- FAQ 表（增加审计字段）
-- ========================================
CREATE TABLE IF NOT EXISTS faqs (
    faq_id VARCHAR(191) PRIMARY KEY,
    course_id VARCHAR(128) NOT NULL,
    question TEXT NOT NULL,
    answer MEDIUMTEXT NOT NULL,
    source VARCHAR(128) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0,
    INDEX idx_faqs_course (course_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 聊天历史表（保持原有）
-- ========================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(191) NOT NULL,
    user_id VARCHAR(191) NULL,
    message LONGTEXT NOT NULL,
    INDEX idx_chat_messages_session_id (session_id),
    INDEX idx_chat_messages_user_id (user_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 用户反馈表（增加时间戳）
-- ========================================
CREATE TABLE IF NOT EXISTS qa_feedback (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(191) NULL,
    course_id VARCHAR(128) NULL,
    question TEXT NOT NULL,
    answer MEDIUMTEXT NOT NULL,
    rating VARCHAR(32) NOT NULL,
    comment TEXT NULL,
    sources_json LONGTEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 【新增】入库进度追踪表
-- ========================================
CREATE TABLE IF NOT EXISTS ingestion_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_path VARCHAR(512) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    kb_version VARCHAR(191) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    chunk_count INT NOT NULL DEFAULT 0,
    error_msg TEXT NULL,
    processed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_file_hash (file_hash, kb_version),
    INDEX idx_status (status)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 【新增】文件注册表（增量同步）
-- ========================================
CREATE TABLE IF NOT EXISTS file_registry (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_path VARCHAR(512) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    kb_version VARCHAR(191) NOT NULL,
    chunk_count INT NOT NULL DEFAULT 0,
    ingested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_file_path (file_path, kb_version),
    INDEX idx_kb_version (kb_version)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 【新增】检索日志表
-- ========================================
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(191) NULL,
    query TEXT NOT NULL,
    intent VARCHAR(32) NULL,
    channel VARCHAR(32) NOT NULL,
    hit_count INT NOT NULL DEFAULT 0,
    top_score FLOAT NULL,
    elapsed_ms INT NULL,
    trace_id VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_retrieval_logs_session (session_id),
    INDEX idx_retrieval_logs_created (created_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 【新增】操作审计日志表
-- ========================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    operator_id VARCHAR(191) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource VARCHAR(191) NULL,
    request_body_hash VARCHAR(64) NULL,
    response_status INT NULL,
    ip VARCHAR(64) NULL,
    user_agent VARCHAR(256) NULL,
    trace_id VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_logs_operator (operator_id),
    INDEX idx_audit_logs_action (action),
    INDEX idx_audit_logs_created (created_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 【新增】学员进度表（个性化检索）
-- ========================================
CREATE TABLE IF NOT EXISTS student_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(191) NOT NULL,
    course_id VARCHAR(128) NOT NULL,
    current_chapter_id VARCHAR(191) NULL,
    mastered_points TEXT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_student_course (user_id, course_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ========================================
-- 【P1 新增】用户表
-- ========================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(191) NOT NULL UNIQUE,
    username VARCHAR(191) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'student',
    course_ids VARCHAR(512) NOT NULL DEFAULT '',
    display_name VARCHAR(191) NULL,
    is_active TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_role (role),
    INDEX idx_users_active (is_active)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;